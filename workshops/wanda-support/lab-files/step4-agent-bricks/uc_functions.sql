-- Step 4: governed tools for Wanda, as Unity Catalog functions over samples.wanderbricks.
-- Replace <catalog> and <schema> with your own (for example your workspace catalog and wanda_support).
-- Run in the SQL editor on a SQL warehouse.

CREATE OR REPLACE FUNCTION <catalog>.<schema>.get_booking(booking_id BIGINT COMMENT 'The booking ID')
RETURNS TABLE (booking_id BIGINT, status STRING, check_in DATE, check_out DATE, guests_count INT,
               total_amount DECIMAL(12, 2), guest_name STRING, guest_country STRING, property STRING,
               payment_status STRING, payment_method STRING, amount_paid DECIMAL(12, 2))
COMMENT 'Look up one Wanderbricks booking: dates, status, guest, property and payment.'
RETURN
  SELECT b.booking_id, b.status, b.check_in, b.check_out, b.guests_count,
         CAST(b.total_amount AS DECIMAL(12, 2)), u.name, u.country, p.title,
         max(pay.status), max(pay.payment_method),
         CAST(coalesce(sum(CASE WHEN pay.status = 'completed' THEN pay.amount END), 0) AS DECIMAL(12, 2))
  FROM samples.wanderbricks.bookings b
  JOIN samples.wanderbricks.users u ON u.user_id = b.user_id
  JOIN samples.wanderbricks.properties p ON p.property_id = b.property_id
  LEFT JOIN samples.wanderbricks.payments pay ON pay.booking_id = b.booking_id
  WHERE b.booking_id = get_booking.booking_id
  GROUP BY ALL;

CREATE OR REPLACE FUNCTION <catalog>.<schema>.list_guest_bookings(user_id BIGINT COMMENT 'The guest user ID')
RETURNS TABLE (booking_id BIGINT, status STRING, check_in DATE, check_out DATE, total_amount DECIMAL(12, 2))
COMMENT 'List a guest''s bookings that check in on or after 1 July 2025 (the lab''s "today").'
RETURN
  SELECT booking_id, status, check_in, check_out, CAST(total_amount AS DECIMAL(12, 2))
  FROM samples.wanderbricks.bookings
  WHERE user_id = list_guest_bookings.user_id AND check_in >= DATE'2025-07-01'
  ORDER BY check_in;

CREATE OR REPLACE FUNCTION <catalog>.<schema>.quote_refund(booking_id BIGINT COMMENT 'The booking ID')
RETURNS TABLE (booking_id BIGINT, total_paid DECIMAL(12, 2), days_before_check_in INT, rule STRING, refund_amount DECIMAL(12, 2))
COMMENT 'Refund a guest gets if they cancel today (1 July 2025) under the Wanderbricks refund policy.'
RETURN
  WITH paid AS (
    SELECT b.booking_id, b.check_in,
           coalesce(sum(CASE WHEN pay.status = 'completed' THEN pay.amount END), 0) AS total_paid
    FROM samples.wanderbricks.bookings b
    LEFT JOIN samples.wanderbricks.payments pay ON pay.booking_id = b.booking_id
    WHERE b.booking_id = quote_refund.booking_id
    GROUP BY ALL
  )
  SELECT booking_id, CAST(total_paid AS DECIMAL(12, 2)), datediff(check_in, DATE'2025-07-01'),
         CASE WHEN total_paid = 0 THEN 'no completed payment, nothing to refund'
              WHEN datediff(check_in, DATE'2025-07-01') >= 14 THEN 'full refund (14 or more days before check-in)'
              WHEN datediff(check_in, DATE'2025-07-01') >= 7 THEN '50% refund (7 to 13 days before check-in)'
              ELSE 'no refund (less than 7 days before check-in)' END,
         CAST(round(CAST(total_paid AS DECIMAL(12, 4)) *
              CASE WHEN datediff(check_in, DATE'2025-07-01') >= 14 THEN 1.0
                   WHEN datediff(check_in, DATE'2025-07-01') >= 7 THEN 0.5 ELSE 0 END, 2) AS DECIMAL(12, 2))
  FROM paid;

CREATE OR REPLACE FUNCTION <catalog>.<schema>.get_refund_policy()
RETURNS STRING
COMMENT 'The Wanderbricks cancellation and refund policy.'
RETURN 'Cancelled 14 or more days before check-in: full refund. Cancelled 7 to 13 days before check-in: 50% refund. Cancelled less than 7 days before check-in: no refund. Only bookings with a completed payment can be refunded. Refunds are paid to the original payment method.';
