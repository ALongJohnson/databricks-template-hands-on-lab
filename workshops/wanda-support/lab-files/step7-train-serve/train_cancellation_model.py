# Databricks notebook source
# MAGIC %md
# MAGIC # Step 7: Train, register and serve a cancellation-risk model
# MAGIC
# MAGIC Trains a classifier that predicts whether a Wanderbricks booking will be cancelled, on
# MAGIC `samples.wanderbricks`. MLflow logs the run, Unity Catalog registers the model, and Model
# MAGIC Serving hosts it on an endpoint that scales to zero. Run it on serverless compute.

# COMMAND ----------

# MAGIC %pip install -q mlflow==3.18.0 scikit-learn==1.7.2 databricks-sdk==0.171.0
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog")
dbutils.widgets.text("schema", "wanda_support", "Schema")
dbutils.widgets.text("endpoint", "wanda-cancellation-risk", "Serving endpoint name")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
ENDPOINT = dbutils.widgets.get("endpoint")
MODEL_NAME = f"{CATALOG}.{SCHEMA}.cancellation_risk"
assert CATALOG, "Set the catalog widget to a catalog you can write to"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Build features from governed tables
# MAGIC Unity Catalog records lineage from `samples.wanderbricks` to the feature table and the model.

# COMMAND ----------

FEATURES = ["lead_days", "nights", "guests_count", "total_amount", "is_business", "check_in_month"]
features = spark.sql(f"""
  SELECT b.booking_id,
         datediff(b.check_in, to_date(b.created_at))    AS lead_days,
         datediff(b.check_out, b.check_in)              AS nights,
         b.guests_count,
         CAST(b.total_amount AS DOUBLE)                 AS total_amount,
         CAST(u.is_business AS INT)                     AS is_business,
         month(b.check_in)                              AS check_in_month,
         CAST(b.status = 'cancelled' AS INT)            AS cancelled
  FROM samples.wanderbricks.bookings b
  JOIN samples.wanderbricks.users u USING (user_id)
  WHERE b.status IN ('cancelled', 'completed', 'confirmed')
""")
features.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.booking_features")
pdf = spark.table(f"{CATALOG}.{SCHEMA}.booking_features").toPandas()
print(f"{len(pdf):,} bookings, {pdf.cancelled.mean():.1%} cancelled")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Train and log with MLflow

# COMMAND ----------

import mlflow
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

mlflow.set_registry_uri("databricks-uc")
X, y = pdf[FEATURES].astype("float64"), pdf["cancelled"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

with mlflow.start_run(run_name="cancellation_risk") as run:
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    mlflow.log_params({"model": "HistGradientBoostingClassifier", "max_iter": 200})
    mlflow.log_metric("test_auc", auc)
    info = mlflow.sklearn.log_model(
        model, name="model", input_example=X_test.head(3),
        signature=infer_signature(X_test, model.predict_proba(X_test)),
        pyfunc_predict_fn="predict_proba", registered_model_name=MODEL_NAME,
    )
print(f"Test AUC: {auc:.3f}. Registered {MODEL_NAME} version {info.registered_model_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Promote with an alias, then serve it

# COMMAND ----------

from mlflow import MlflowClient
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

version = info.registered_model_version
MlflowClient().set_registered_model_alias(MODEL_NAME, "champion", version)

w = WorkspaceClient()
served = [ServedEntityInput(entity_name=MODEL_NAME, entity_version=str(version),
                            workload_size="Small", scale_to_zero_enabled=True)]
if any(e.name == ENDPOINT for e in w.serving_endpoints.list()):
    w.serving_endpoints.update_config_and_wait(name=ENDPOINT, served_entities=served)
else:
    w.serving_endpoints.create_and_wait(name=ENDPOINT, config=EndpointCoreConfigInput(name=ENDPOINT, served_entities=served))
print(f"Endpoint {ENDPOINT} is ready and scales to zero when idle")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Test the endpoint

# COMMAND ----------

sample = X_test.head(2).to_dict(orient="records")
print(w.serving_endpoints.query(name=ENDPOINT, dataframe_records=sample).predictions)
