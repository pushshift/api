import psycopg2
import time
from configparser import ConfigParser

config = ConfigParser()
config.read('credentials.ini')


class pgdb:

    def __init__(self):
        self.connect()

    def connect(self):
        DB_PASSWORD = config.get('database', 'password')
        DB_USER = config.get('database', 'user')
        self.db = psycopg2.connect(
            "dbname='reddit' user='" + DB_USER + "' host='jupiter' password='" + DB_PASSWORD + "'")
        self.db.set_session(autocommit=True)

    def execute(self, sql, params):
        retries = 5
        while True:
            retries -= 1
            try:
                cur = self.db.cursor()
                cur.execute(sql, (params,))
                rows = cur.fetchall()
                cur.close()
                return rows
            except:
                if retries <= 0:
                    raise
                try:
                    time.sleep(1)
                    self.connect()
                except:
                    raise


pgdb = pgdb()
