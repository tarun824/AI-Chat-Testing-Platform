from typing import Any, Dict, List

DEFAULT_CASE_LIBRARY: Dict[str, List[Dict[str, Any]]] = {
    "appointment": [
        {"id": "appointment_book", "tags": ["appointment"], "text": "I want to book an appointment for next week."},
        {"id": "appointment_reschedule", "tags": ["appointment"], "text": "Please reschedule my appointment to another day."},
        {"id": "appointment_cancel", "tags": ["appointment"], "text": "Cancel my appointment, please."},
    ],
    "appointment_nlp": [
        {"id": "appointment_nlp_monday", "tags": ["appointment_nlp", "appointment"], "text": "Book me for Monday morning if available."},
        {"id": "appointment_nlp_followup", "tags": ["appointment_nlp", "appointment"], "text": "Schedule a follow-up appointment next week."},
        {"id": "appointment_nlp_slots", "tags": ["appointment_nlp", "appointment"], "text": "What slots are open for consultation?"},
    ],
    "patient_appointment": [
        {"id": "patient_appointment_book", "tags": ["patient_appointment", "appointment"], "text": "I need an appointment with a doctor."},
        {"id": "patient_appointment_change", "tags": ["patient_appointment", "appointment"], "text": "Can I change my appointment time?"},
        {"id": "patient_appointment_availability", "tags": ["patient_appointment", "appointment"], "text": "Is there any availability this week?"},
    ],
    "patient_promotion": [
        {"id": "patient_promotion_offers", "tags": ["patient_promotion", "promotion"], "text": "Do you have any IVF offers right now?"},
        {"id": "patient_promotion_packages", "tags": ["patient_promotion", "promotion"], "text": "Share your packages and pricing."},
        {"id": "patient_promotion_discount", "tags": ["patient_promotion", "promotion"], "text": "Any discounts available this month?"},
    ],
    "patient_query": [
        {"id": "patient_query_fees", "tags": ["patient_query"], "text": "What are your consultation charges?"},
        {"id": "patient_query_services", "tags": ["patient_query"], "text": "What treatments do you provide?"},
        {"id": "patient_query_location", "tags": ["patient_query"], "text": "Where is your clinic located?"},
    ],
    "doctor": [
        {"id": "doctor_info", "tags": ["doctor"], "text": "Can you share details about your doctors?"},
        {"id": "doctor_experience", "tags": ["doctor"], "text": "How experienced are your doctors?"},
        {"id": "doctor_availability", "tags": ["doctor"], "text": "Which doctor is available this week?"},
    ],
    "qna": [
        {"id": "qna_timings", "tags": ["qna"], "text": "What are your clinic timings today?"},
        {"id": "qna_working_days", "tags": ["qna"], "text": "Are you open on Sundays?"},
        {"id": "qna_contact", "tags": ["qna"], "text": "How can I contact your clinic?"},
    ],
    "care_coordinator": [
        {"id": "care_coordinator_help", "tags": ["care_coordinator"], "text": "I need help coordinating my treatment plan."},
        {"id": "care_coordinator_assign", "tags": ["care_coordinator"], "text": "Can you assign a care coordinator for me?"},
        {"id": "care_coordinator_followup", "tags": ["care_coordinator"], "text": "I need follow-up support for my treatment."},
    ],
    "postops": [
        {"id": "postops_pain", "tags": ["postops"], "text": "I had a procedure yesterday and I am feeling pain."},
        {"id": "postops_medication", "tags": ["postops"], "text": "What medicines should I take after surgery?"},
        {"id": "postops_precautions", "tags": ["postops"], "text": "Any precautions I should follow after the procedure?"},
    ],
    "product": [
        {"id": "product_pricing", "tags": ["product"], "text": "Share product pricing and details."},
        {"id": "product_package", "tags": ["product"], "text": "Tell me about your IVF package."},
        {"id": "product_brochure", "tags": ["product"], "text": "Do you have a brochure for your services?"},
    ],
    "negotiator": [
        {"id": "negotiator_price", "tags": ["negotiator"], "text": "Can you provide a better price for the package?"},
        {"id": "negotiator_discount", "tags": ["negotiator"], "text": "Is there any flexibility on pricing?"},
        {"id": "negotiator_offer", "tags": ["negotiator"], "text": "Match a lower quote I received elsewhere."},
    ],
    "partner": [
        {"id": "partner_query", "tags": ["partner"], "text": "I want to partner with your clinic. How do we proceed?"},
        {"id": "partner_referral", "tags": ["partner"], "text": "Do you have a referral or partnership program?"},
        {"id": "partner_corporate", "tags": ["partner"], "text": "Interested in a corporate tie-up. Please share details."},
    ],
    "madhavbaug": [
        {"id": "madhavbaug_about", "tags": ["madhavbaug"], "text": "Tell me about the Madhavbaug program."},
        {"id": "madhavbaug_eligibility", "tags": ["madhavbaug"], "text": "Who is eligible for Madhavbaug treatment?"},
        {"id": "madhavbaug_pricing", "tags": ["madhavbaug"], "text": "What is the pricing for Madhavbaug services?"},
    ],
    "router": [
        {"id": "router_general", "tags": ["router"], "text": "Hello, I need help with my treatment."},
        {"id": "router_confused", "tags": ["router"], "text": "I am not sure what I need. Can you help?"},
        {"id": "router_services", "tags": ["router"], "text": "Can you guide me on the next steps?"},
    ],
    "proactive_router": [
        {"id": "proactive_router_followup", "tags": ["proactive_router"], "text": "I missed your call. Please follow up."},
        {"id": "proactive_router_offer", "tags": ["proactive_router", "promotion"], "text": "Are there any special offers for me?"},
        {"id": "proactive_router_schedule", "tags": ["proactive_router", "appointment"], "text": "Can you schedule a quick call with me?"},
    ],
    "summarizing": [
        {"id": "summarizing_chat", "tags": ["summarizing"], "text": "Please summarize my recent conversation."},
        {"id": "summarizing_treatment", "tags": ["summarizing"], "text": "Summarize my treatment plan details."},
        {"id": "summarizing_next_steps", "tags": ["summarizing"], "text": "Summarize the next steps for me."},
    ],
    "track_progress": [
        {"id": "track_progress_status", "tags": ["track_progress"], "text": "Can you tell me my treatment progress status?"},
        {"id": "track_progress_update", "tags": ["track_progress"], "text": "Any update on my progress?"},
        {"id": "track_progress_report", "tags": ["track_progress"], "text": "Share my progress report."},
    ],
    "reminder": [
        {"id": "reminder_request", "tags": ["reminder"], "text": "Please remind me about my appointment tomorrow."},
        {"id": "reminder_medicine", "tags": ["reminder"], "text": "Set a reminder for my medicine schedule."},
        {"id": "reminder_followup", "tags": ["reminder"], "text": "Remind me for my follow-up visit."},
    ],
    "media_success": [
        {"id": "media_success_report", "tags": ["media_success"], "text": "I have uploaded my report."},
        {"id": "media_success_document", "tags": ["media_success"], "text": "Please confirm if my document is received."},
        {"id": "media_success_image", "tags": ["media_success"], "text": "I sent an image. Did you get it?"},
    ],
    "media_sucess": [
        {"id": "media_sucess_report", "tags": ["media_sucess"], "text": "I uploaded my lab report."},
        {"id": "media_sucess_document", "tags": ["media_sucess"], "text": "Please check my uploaded files."},
        {"id": "media_sucess_image", "tags": ["media_sucess"], "text": "I shared a document just now."},
    ],
    "consent": [
        {"id": "consent_yes", "tags": ["consent"], "text": "Yes, I consent to the terms."},
        {"id": "consent_info", "tags": ["consent"], "text": "Please explain the consent process."},
        {"id": "consent_confirm", "tags": ["consent"], "text": "I agree to proceed."},
    ],
    "agents": [
        {"id": "agents_appointment", "tags": ["agents", "appointment"], "text": "I want to book an appointment."},
        {"id": "agents_query", "tags": ["agents", "patient_query"], "text": "Tell me about your services and pricing."},
        {"id": "agents_promotion", "tags": ["agents", "promotion"], "text": "Do you have any offers?"},
    ],
    "mixed": [
        {"id": "mixed_query", "tags": ["mixed", "patient_query"], "text": "What are the consultation fees?"},
        {"id": "mixed_appointment", "tags": ["mixed", "appointment"], "text": "Book an appointment for next week."},
        {"id": "mixed_promotion", "tags": ["mixed", "promotion"], "text": "Share your latest packages or offers."},
    ],
    "default": [
        {"id": "default_ping", "tags": ["auto"], "text": "Hello, I need help."},
        {"id": "default_info", "tags": ["auto"], "text": "Please share more information."},
        {"id": "default_support", "tags": ["auto"], "text": "I want to talk to support."},
    ],
}
