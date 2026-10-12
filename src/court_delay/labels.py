"""Constants shared by training and the API, with no third-party imports (the API stays small)."""

CRIMINAL = {
    "summary_criminal", "regular_criminal", "sessions_special", "bail_remand",
    "criminal_misc", "criminal_appeal_revision", "domestic_violence", "juvenile",
}
CIVIL = {
    "civil_suit", "civil_appeal_revision", "civil_misc", "execution", "motor_accident",
    "land_acquisition", "arbitration_cooperative", "family", "labour", "succession",
}

# Mumbai court systems and statewide tribunals in DDL's district key (D-009).
COURT_SYSTEM_PATTERN = r"^(Mumbai|Maharashtra|Mah )"
