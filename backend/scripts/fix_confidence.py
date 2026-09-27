import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='journi', user='journi', password='123456')
cur = conn.cursor()
cur.execute("UPDATE places SET confidence = NULL WHERE source != 'JOURNI Curated'")
conn.commit()
conn.close()
print("Updated confidence to NULL")
