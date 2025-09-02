import sqlite3

# Connect to the database
conn = sqlite3.connect('instance/adghm.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print('Database tables:')
for table in tables:
    print(f'- {table[0]}')

# Check users table structure if it exists
if any('users' in table for table in tables):
    print('\nUsers table columns:')
    cursor.execute("PRAGMA table_info(users);")
    columns = cursor.fetchall()
    for column in columns:
        print(f'- {column[1]} ({column[2]})')
else:
    print('\nUsers table does not exist!')

# Check vip_config table structure if it exists
if any('vip_config' in table for table in tables):
    print('\nVIP Config table columns:')
    cursor.execute("PRAGMA table_info(vip_config);")
    columns = cursor.fetchall()
    for column in columns:
        print(f'- {column[1]} ({column[2]})')
else:
    print('\nVIP Config table does not exist!')

conn.close()