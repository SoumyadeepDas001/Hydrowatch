import os
import sys
import sqlite3
from datetime import datetime, timedelta
from schema.bq_schema import StorageManager, DB_NAME

def clean_local_db():
    """Wipes the local database tables if running in SQLite fallback mode to start fresh."""
    if os.path.exists(DB_NAME):
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM readings")
            cursor.execute("DELETE FROM alerts")
            conn.commit()
            conn.close()
            print("Successfully cleared local SQLite tables for fresh seeding.")
        except Exception as e:
            print(f"Error clearing local SQLite tables: {e}")

def main():
    print("Initializing HydroWatch Database Seeding...")
    
    # Clean SQLite db first for fresh run
    clean_local_db()
    
    storage = StorageManager()
    
    base_date = datetime(2026, 6, 1, 12, 0, 0)
    
    # --- Source 1: Normal Borewell in Rampur ---
    print("Seeding Source 1 (SRC-BOR-0001) - Normal readings (pH + Fluoride)...")
    for i in range(5):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0001",
            village_id="VIL-RAM-001",
            parameter="ph",
            value=7.2 + (i * 0.05),
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-ASHA-001"
        )
        storage.log_reading(
            source_id="SRC-BOR-0001",
            village_id="VIL-RAM-001",
            parameter="fluoride",
            value=0.6,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-001"
        )

    # --- Source 2: Acute Arsenic Breach in Rampur ---
    print("Seeding Source 2 (SRC-BOR-0002) - Acute Arsenic Breach...")
    for i in range(4):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0002",
            village_id="VIL-RAM-001",
            parameter="arsenic",
            value=0.005,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-001"
        )
    # The breach
    breach_date = (base_date + timedelta(days=4)).isoformat()
    storage.log_reading(
        source_id="SRC-BOR-0002",
        village_id="VIL-RAM-001",
        parameter="arsenic",
        value=0.025, # Limit is 0.01
        unit="mg/L",
        date_str=breach_date,
        reported_by_id="REP-ASHA-001"
    )

    # --- Source 3: Slow Fluoride Drift in Rampur ---
    print("Seeding Source 3 (SRC-BOR-0003) - Slow Fluoride Drift...")
    fluoride_values = [1.1, 1.2, 1.3, 1.4, 1.6]
    for i, val in enumerate(fluoride_values):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0003",
            village_id="VIL-RAM-001",
            parameter="fluoride",
            value=val,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-002"
        )

    # --- Source 4: E. Coli Breach in Sundarpur ---
    print("Seeding Source 4 (SRC-WEL-0001) - Bacterial Contamination...")
    for i in range(2):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-WEL-0001",
            village_id="VIL-SUN-002",
            parameter="bacterial counts",
            value=0.0,
            unit="CFU/100mL",
            date_str=date,
            reported_by_id="REP-ASHA-003"
        )
    # Breach
    bact_breach_date = (base_date + timedelta(days=2)).isoformat()
    storage.log_reading(
        source_id="SRC-WEL-0001",
        village_id="VIL-SUN-002",
        parameter="bacterial counts",
        value=15.0, # Limit is 0.0
        unit="CFU/100mL",
        date_str=bact_breach_date,
        reported_by_id="REP-ASHA-003"
    )

    # --- Source 5: Normal Handpump in Haripur ---
    print("Seeding Source 5 (SRC-HDP-0001) - Normal Handpump (Turbidity + pH)...")
    for i in range(3):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-HDP-0001",
            village_id="VIL-HAR-003",
            parameter="turbidity",
            value=1.5,
            unit="NTU",
            date_str=date,
            reported_by_id="REP-VOL-011"
        )
        storage.log_reading(
            source_id="SRC-HDP-0001",
            village_id="VIL-HAR-003",
            parameter="ph",
            value=7.0,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-VOL-011"
        )

    # --- Source 6: Watchlist Turbidity Drift in Beldanga ---
    print("Seeding Source 6 (SRC-WEL-0002) - Turbidity Drift (Turbidity + Fluoride)...")
    turbidity_vals = [2.0, 2.5, 3.0, 3.5, 4.0] # Limit is 5.0, 4.0 is within 25% (3.75)
    for i, val in enumerate(turbidity_vals):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-WEL-0002",
            village_id="VIL-BEL-004",
            parameter="turbidity",
            value=val,
            unit="NTU",
            date_str=date,
            reported_by_id="REP-VOL-012"
        )
        storage.log_reading(
            source_id="SRC-WEL-0002",
            village_id="VIL-BEL-004",
            parameter="fluoride",
            value=0.5,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-VOL-012"
        )

    # --- Source 7: Normal Handpump in Sundarpur ---
    print("Seeding Source 7 (SRC-HDP-0002) - Normal (Arsenic + pH)...")
    for i in range(3):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-HDP-0002",
            village_id="VIL-SUN-002",
            parameter="arsenic",
            value=0.002,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-003"
        )
        storage.log_reading(
            source_id="SRC-HDP-0002",
            village_id="VIL-SUN-002",
            parameter="ph",
            value=7.1,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-ASHA-003"
        )

    # --- Source 8: Watchlist Fluoride Drift in Haripur ---
    print("Seeding Source 8 (SRC-BOR-0004) - Fluoride Drift (Fluoride + Arsenic)...")
    fluoride_vals = [0.8, 0.9, 1.0, 1.2, 1.35] # Limit is 1.5, 1.35 is within 25% (1.125)
    for i, val in enumerate(fluoride_vals):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0004",
            village_id="VIL-HAR-003",
            parameter="fluoride",
            value=val,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-VOL-011"
        )
        storage.log_reading(
            source_id="SRC-BOR-0004",
            village_id="VIL-HAR-003",
            parameter="arsenic",
            value=0.003,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-VOL-011"
        )
    # --- Source 9: Watchlist Nitrate Drift in Bankura Rural ---
    print("Seeding Source 9 (SRC-BOR-0005) - Watchlist Nitrate Drift...")
    nitrate_vals_9 = [28.0, 30.0, 32.0, 34.0, 36.0]
    for i, val in enumerate(nitrate_vals_9):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0005",
            village_id="VIL-BAK-005",
            parameter="nitrate",
            value=val,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-005"
        )
        storage.log_reading(
            source_id="SRC-BOR-0005",
            village_id="VIL-BAK-005",
            parameter="ph",
            value=7.2,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-ASHA-005"
        )

    # --- Source 10: Normal Handpump in Bishnupur Peri-Urban ---
    print("Seeding Source 10 (SRC-HDP-0003) - Normal...")
    for i in range(3):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-HDP-0003",
            village_id="VIL-BIS-006",
            parameter="ph",
            value=7.0,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-VOL-020"
        )
        storage.log_reading(
            source_id="SRC-HDP-0003",
            village_id="VIL-BIS-006",
            parameter="turbidity",
            value=1.2,
            unit="NTU",
            date_str=date,
            reported_by_id="REP-VOL-020"
        )
        storage.log_reading(
            source_id="SRC-HDP-0003",
            village_id="VIL-BIS-006",
            parameter="nitrate",
            value=10.0,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-VOL-020"
        )

    # --- Source 11: Watchlist pH Drift (Downward) in Kakdwip Coastal ---
    print("Seeding Source 11 (SRC-SRF-0001) - pH Drift Down...")
    ph_vals_11 = [7.4, 7.2, 7.0, 6.9, 6.7]
    for i, val in enumerate(ph_vals_11):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-SRF-0001",
            village_id="VIL-KAK-007",
            parameter="ph",
            value=val,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-ASHA-007"
        )

    # --- Source 12: Immediate Hazard Arsenic in Habra East ---
    print("Seeding Source 12 (SRC-BOR-0006) - Immediate Hazard Arsenic...")
    arsenic_vals_12 = [0.003, 0.003, 0.003, 0.003, 0.012]
    for i, val in enumerate(arsenic_vals_12):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0006",
            village_id="VIL-HAB-008",
            parameter="arsenic",
            value=val,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-008"
        )
        storage.log_reading(
            source_id="SRC-BOR-0006",
            village_id="VIL-HAB-008",
            parameter="nitrate",
            value=12.0,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-008"
        )

    # --- Source 13: Normal in Kalyani Sector 3 ---
    print("Seeding Source 13 (SRC-HDP-0004) - Normal...")
    for i in range(3):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-HDP-0004",
            village_id="VIL-KAL-009",
            parameter="ph",
            value=7.4,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-VOL-021"
        )
        storage.log_reading(
            source_id="SRC-HDP-0004",
            village_id="VIL-KAL-009",
            parameter="bacterial counts",
            value=0.0,
            unit="CFU/100mL",
            date_str=date,
            reported_by_id="REP-VOL-021"
        )

    # --- Source 14: Normal in Singur Farmstead ---
    print("Seeding Source 14 (SRC-SRF-0002) - Normal...")
    for i in range(3):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-SRF-0002",
            village_id="VIL-SIN-010",
            parameter="turbidity",
            value=2.0,
            unit="NTU",
            date_str=date,
            reported_by_id="REP-VOL-022"
        )

    # --- Source 15: Watchlist Arsenic Drift in Tarakeswar ---
    print("Seeding Source 15 (SRC-BOR-0007) - Watchlist Arsenic Drift...")
    arsenic_vals_15 = [0.005, 0.006, 0.007, 0.008, 0.009]
    for i, val in enumerate(arsenic_vals_15):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0007",
            village_id="VIL-TAR-011",
            parameter="arsenic",
            value=val,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-025"
        )

    # --- Source 16: Normal in Bolpur Rural ---
    print("Seeding Source 16 (SRC-HDP-0005) - Normal...")
    for i in range(3):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-HDP-0005",
            village_id="VIL-BOL-012",
            parameter="ph",
            value=7.2,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-ASHA-026"
        )

    # --- Source 17: Watchlist pH Drift (Upward) in Illambazar ---
    print("Seeding Source 17 (SRC-SRF-0003) - pH Drift Up...")
    ph_vals_17 = [7.5, 7.7, 7.9, 8.1, 8.2]
    for i, val in enumerate(ph_vals_17):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-SRF-0003",
            village_id="VIL-ILL-013",
            parameter="ph",
            value=val,
            unit="pH Units",
            date_str=date,
            reported_by_id="REP-ASHA-027"
        )

    # --- Source 18: Immediate Hazard Nitrate in Gushkara West ---
    print("Seeding Source 18 (SRC-BOR-0008) - Immediate Hazard Nitrate...")
    nitrate_vals_18 = [20.0, 25.0, 48.0]
    for i, val in enumerate(nitrate_vals_18):
        date = (base_date + timedelta(days=i)).isoformat()
        storage.log_reading(
            source_id="SRC-BOR-0008",
            village_id="VIL-GUS-014",
            parameter="nitrate",
            value=val,
            unit="mg/L",
            date_str=date,
            reported_by_id="REP-ASHA-028"
        )

    # --- Seeding Alerts History ---
    print("\nSeeding Alerts history...")
    alert_date_base = base_date + timedelta(days=4)
    
    # 1. Acute arsenic alert for SRC-BOR-0002 (Drafted)
    storage.save_alert(
        alert_id="ALT-ARS-0002",
        source_id="SRC-BOR-0002",
        village_id="VIL-RAM-001",
        severity="IMMEDIATE_HAZARD",
        message="[URGENT PUBLIC HEALTH ALERT] Critical contamination detected at water source SRC-BOR-0002 in village VIL-RAM-001. Exposure risks present. Immediate shutoff or warning required.",
        recipient="health_officer_rampur@gov.in",
        timestamp_str=(alert_date_base - timedelta(hours=2)).isoformat(),
        status="drafted"
    )
    
    # 2. Rate-limited alert for SRC-BOR-0002 (Rate Limited)
    storage.save_alert(
        alert_id="ALT-ARS-0002-RL",
        source_id="SRC-BOR-0002",
        village_id="VIL-RAM-001",
        severity="IMMEDIATE_HAZARD",
        message="Alert was suppressed due to 48-hour rate limit on IMMEDIATE_HAZARD notifications.",
        recipient="health_officer_rampur@gov.in",
        timestamp_str=(alert_date_base - timedelta(hours=1)).isoformat(),
        status="rate_limited"
    )

    # 3. Watchlist digest for SRC-BOR-0003 (Drafted)
    storage.save_alert(
        alert_id="ALT-FLU-0003",
        source_id="SRC-BOR-0003",
        village_id="VIL-RAM-001",
        severity="WATCHLIST",
        message="[WATCHLIST DIGEST] Water source SRC-BOR-0003 in village VIL-RAM-001 has demonstrated a slow-drift contamination trend over recent readings. Remedial maintenance recommended.",
        recipient="health_officer_rampur@gov.in",
        timestamp_str=(base_date + timedelta(days=3)).isoformat(),
        status="drafted"
    )

    # 4. Acute fluoride breach alert for SRC-BOR-0003 (Drafted)
    storage.save_alert(
        alert_id="ALT-FLU-0003-HAZ",
        source_id="SRC-BOR-0003",
        village_id="VIL-RAM-001",
        severity="IMMEDIATE_HAZARD",
        message="[URGENT PUBLIC HEALTH ALERT] Critical contamination detected at water source SRC-BOR-0003 in village VIL-RAM-001. Exposure risks present. Immediate shutoff or warning required.",
        recipient="health_officer_rampur@gov.in",
        timestamp_str=alert_date_base.isoformat(),
        status="drafted"
    )

    # 5. Bacterial contamination alert for SRC-WEL-0001 (Sent)
    storage.save_alert(
        alert_id="ALT-BAC-0001",
        source_id="SRC-WEL-0001",
        village_id="VIL-SUN-002",
        severity="IMMEDIATE_HAZARD",
        message="[URGENT PUBLIC HEALTH ALERT] Critical contamination detected at water source SRC-WEL-0001 in village VIL-SUN-002. Exposure risks present. Immediate shutoff or warning required.",
        recipient="health_officer_sundarpur@gov.in",
        timestamp_str=(base_date + timedelta(days=2)).isoformat(),
        status="sent"
    )

    # 6. Watchlist digest for SRC-WEL-0002 (Drafted)
    storage.save_alert(
        alert_id="ALT-TUR-0002",
        source_id="SRC-WEL-0002",
        village_id="VIL-BEL-004",
        severity="WATCHLIST",
        message="[WATCHLIST DIGEST] Water source SRC-WEL-0002 in village VIL-BEL-004 has demonstrated a slow-drift contamination trend over recent readings. Remedial maintenance recommended.",
        recipient="health_officer_beldanga@gov.in",
        timestamp_str=(base_date + timedelta(days=4)).isoformat(),
        status="drafted"
    )

    # 7. Watchlist digest for SRC-BOR-0004 (Drafted)
    storage.save_alert(
        alert_id="ALT-FLU-0004",
        source_id="SRC-BOR-0004",
        village_id="VIL-HAR-003",
        severity="WATCHLIST",
        message="[WATCHLIST DIGEST] Water source SRC-BOR-0004 in village VIL-HAR-003 has demonstrated a slow-drift contamination trend over recent readings. Remedial maintenance recommended.",
        recipient="health_officer_haripur@gov.in",
        timestamp_str=(base_date + timedelta(days=4)).isoformat(),
        status="drafted"
    )

    # 8. Watchlist digest for SRC-BOR-0005 (Drafted)
    storage.save_alert(
        alert_id="ALT-NIT-0005",
        source_id="SRC-BOR-0005",
        village_id="VIL-BAK-005",
        severity="WATCHLIST",
        message="[WATCHLIST DIGEST] Water source SRC-BOR-0005 in Bankura Rural (VIL-BAK-005) has demonstrated a slow-drift contamination trend for nitrate. Remedial monitoring recommended.",
        recipient="health_officer_bankura@gov.in",
        timestamp_str=(base_date + timedelta(days=4)).isoformat(),
        status="drafted"
    )

    # 9. Watchlist digest for SRC-SRF-0001 (Drafted)
    storage.save_alert(
        alert_id="ALT-PH-0001",
        source_id="SRC-SRF-0001",
        village_id="VIL-KAK-007",
        severity="WATCHLIST",
        message="[WATCHLIST DIGEST] Water source SRC-SRF-0001 in Kakdwip Coastal (VIL-KAK-007) has demonstrated pH drift downward. Remedial monitoring recommended.",
        recipient="health_officer_kakdwip@gov.in",
        timestamp_str=(base_date + timedelta(days=4)).isoformat(),
        status="drafted"
    )

    # 10. Acute arsenic alert for SRC-BOR-0006 (Drafted)
    storage.save_alert(
        alert_id="ALT-ARS-0006",
        source_id="SRC-BOR-0006",
        village_id="VIL-HAB-008",
        severity="IMMEDIATE_HAZARD",
        message="[URGENT PUBLIC HEALTH ALERT] Critical contamination detected at water source SRC-BOR-0006 in village VIL-HAB-008 (Habra East). Exposure risks present. Immediate warning required.",
        recipient="health_officer_habra@gov.in",
        timestamp_str=(base_date + timedelta(days=4)).isoformat(),
        status="drafted"
    )

    # 11. Watchlist digest for SRC-BOR-0007 (Drafted)
    storage.save_alert(
        alert_id="ALT-ARS-0007",
        source_id="SRC-BOR-0007",
        village_id="VIL-TAR-011",
        severity="WATCHLIST",
        message="[WATCHLIST DIGEST] Water source SRC-BOR-0007 in Tarakeswar (VIL-TAR-011) has demonstrated a slow arsenic drift trend. Remedial monitoring recommended.",
        recipient="health_officer_tarakeswar@gov.in",
        timestamp_str=(base_date + timedelta(days=4)).isoformat(),
        status="drafted"
    )

    # 12. Acute nitrate alert for SRC-BOR-0008 (Sent)
    storage.save_alert(
        alert_id="ALT-NIT-0008",
        source_id="SRC-BOR-0008",
        village_id="VIL-GUS-014",
        severity="IMMEDIATE_HAZARD",
        message="[URGENT PUBLIC HEALTH ALERT] Critical contamination detected at water source SRC-BOR-0008 in village VIL-GUS-014 (Gushkara West). Exposure risks present. Immediate warnings required.",
        recipient="health_officer_gushkara@gov.in",
        timestamp_str=(base_date + timedelta(days=2)).isoformat(),
        status="sent"
    )

    print("\nDatabase seeding completed successfully!")

if __name__ == "__main__":
    main()
