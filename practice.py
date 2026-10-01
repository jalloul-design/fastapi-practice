import sqlite3

conn = sqlite3.connect('sales.db')

query = """ WITH representative_totals AS( 
    SELECT representatives.store_id, representatives.name, SUM(sales.amount) AS total_sales
    FROM sales 
    JOIN representatives on sales.representative_id = representatives.id
    GROUP BY representatives.id
    )
    SELECT store_id, name, total_sales,
    RANK() OVER(PARTITION BY store_id ORDER BY total_sales DESC) AS rank_in_store
    FROM representative_totals
           """
cursor = conn.cursor()
cursor.execute(query)
for row in cursor.fetchall():
    print(row)

conn.close()