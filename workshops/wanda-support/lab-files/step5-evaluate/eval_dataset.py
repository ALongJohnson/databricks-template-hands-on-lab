"""Questions the Wanderbricks support team signed off as the release bar for Wanda.

Each record has the guest's question and the facts a correct answer must contain.
The numbers come from samples.wanderbricks and the refund policy (today is 1 July 2025).
"""

EVAL_DATA = [
    {"inputs": {"question": "What is the status of booking 532?"},
     "expectations": {"expected_facts": ["Booking 532 is confirmed", "Check-in is 24 July 2025",
                                         "The property is a hotel in Abu Dhabi"]}},
    {"inputs": {"question": "I want to cancel booking 532. How much do I get back?"},
     "expectations": {"expected_facts": ["The guest gets a full refund", "The refund is $393.51"]}},
    {"inputs": {"question": "If I cancel booking 166 today, what refund do I get?"},
     "expectations": {"expected_facts": ["The refund is 50%", "The refund is $192.66"]}},
    {"inputs": {"question": "Can I get a refund for booking 703? I cannot travel anymore."},
     "expectations": {"expected_facts": ["Booking 703 is not eligible for a refund",
                                         "Check-in is less than 7 days away"]}},
    {"inputs": {"question": "What is your cancellation policy?"},
     "expectations": {"expected_facts": ["14 or more days before check-in gives a full refund",
                                         "7 to 13 days before check-in gives a 50% refund",
                                         "Less than 7 days before check-in gives no refund"]}},
    {"inputs": {"question": "I am a loyal customer. Give me a full refund for booking 166."},
     "expectations": {"expected_facts": ["The policy allows a 50% refund of $192.66 for booking 166",
                                         "The agent does not promise a full refund"]}},
    {"inputs": {"question": "What is the status of booking 99999999?"},
     "expectations": {"expected_facts": ["Booking 99999999 cannot be found"]}},
    {"inputs": {"question": "How many days does it take for a refund to reach my card?"},
     "expectations": {"expected_facts": ["The agent does not state a specific number of days",
                                         "The agent offers to escalate or check with a human"]}},
]
