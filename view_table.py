import sqlite3

# Connect to the database
conn = sqlite3.connect("investment_signals.db")
cursor = conn.cursor()

print("\n📊 --- DATABASE REPORT ---")

# 1. Check the Candidates History (Everything found & filtered)
try:
    count_history = cursor.execute("SELECT COUNT(*) FROM metrics_history").fetchone()[0]
    print(f"🔎 Total Repos Scanned (History): {count_history}")
except:
    print("🔎 Total Repos Scanned: 0 (Table not found)")

print("-" * 30)

# 2. Check the AI Judgments (Processed Deals)
try:
    rows = cursor.execute("SELECT title, decision, score, velocity FROM processed_items").fetchall()
    print(f"⚖️  Total AI Judgments: {len(rows)}\n")

    print(f"{'DECISION':<10} | {'SCORE':<5} | {'VELOCITY':<8} | {'TITLE'}")
    print("-" * 60)
    
    for row in rows:
        title = row[0]
        decision = row[1]
        score = row[2]
        velocity = row[3]
        
        # Color coding for terminal
        icon = "✅" if decision == "PUBLISH" else "❌"
        print(f"{icon} {decision:<8} | {score:<5} | {velocity:<8} | {title}")

except Exception as e:
    print(f"⚠️ Could not read processed items: {e}")

print("\n")
conn.close()