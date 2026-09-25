"""
app/infrastructure/db/migrate_inventory.py
Additive migration for inventory table separation:
  - Adds available column (synced with is_active)
  - Adds idx_inventory_lookup and idx_inventory_item_branch
  - Ensures full coverage for branch_id=1 and branch_id=2
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "theatom_local.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check columns on inventory
    cols = [col[1] for col in cursor.execute("PRAGMA table_info(inventory)").fetchall()]

    if "available" not in cols:
        print("Adding 'available' column to inventory table...")
        cursor.execute("ALTER TABLE inventory ADD COLUMN available INTEGER DEFAULT 1;")
        cursor.execute("UPDATE inventory SET available = is_active WHERE available IS NULL;")

    # Create indexes
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_item_branch 
        ON inventory (menu_item_id, branch_id);
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inventory_lookup 
        ON inventory (menu_item_id, branch_id, is_active, stock_quantity);
    """)

    # Ensure branch 1 has all 84 items
    menu_items = cursor.execute("SELECT id FROM menu_items").fetchall()
    for (m_id,) in menu_items:
        row_b1 = cursor.execute("SELECT id FROM inventory WHERE menu_item_id = ? AND branch_id = 1", (m_id,)).fetchone()
        if not row_b1:
            cursor.execute("""
                INSERT INTO inventory (menu_item_id, branch_id, stock_quantity, expiry_date, is_active, available)
                VALUES (?, 1, 50, datetime('now', '+30 days'), 1, 1)
            """, (m_id,))

        # Seed branch 2 for multi-branch isolation testing
        row_b2 = cursor.execute("SELECT id FROM inventory WHERE menu_item_id = ? AND branch_id = 2", (m_id,)).fetchone()
        if not row_b2:
            cursor.execute("""
                INSERT INTO inventory (menu_item_id, branch_id, stock_quantity, expiry_date, is_active, available)
                VALUES (?, 2, 50, datetime('now', '+30 days'), 1, 1)
            """, (m_id,))

    conn.commit()
    count_b1 = cursor.execute("SELECT COUNT(*) FROM inventory WHERE branch_id = 1").fetchone()[0]
    count_b2 = cursor.execute("SELECT COUNT(*) FROM inventory WHERE branch_id = 2").fetchone()[0]
    print(f"Migration complete: branch 1 has {count_b1} items, branch 2 has {count_b2} items.")
    conn.close()

if __name__ == "__main__":
    migrate()
