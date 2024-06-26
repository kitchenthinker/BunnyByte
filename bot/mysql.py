import config
import pymysql
import pymysql.cursors


class MYSQL:
    _instance = None  # Keep instance reference

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.connection = pymysql.connect(host=config.mSQL_H,
                                          user=config.mSQL_L,
                                          password=config.mSQL_P,
                                          database=config.mSQL_DB,
                                          cursorclass=pymysql.cursors.DictCursor,
                                          )
        self.cursor = self.connection.cursor()
        self.data = None
        self.rowcount: int = 0
        self.empty: bool = True

    def get_data(self, user_query: str, values=None):
        c = self.connection
        with c.cursor() as cursor:
            cursor.execute(user_query, values)
            self.data = cursor.fetchall()
            self.rowcount = cursor.rowcount
            self._data_is_empty()

    # PRIVATE
    def refresh(self):
        self.connection.ping()

    def close(self):
        self.connection.close()

    def _data_is_empty(self):
        self.empty = self.rowcount == 0

    def execute(self, user_query: str, values=None, commit=False, close_connection: bool = False):
        self.refresh()
        cursor = self.cursor
        cursor.execute(user_query, values)
        if commit:
            self.commit(close_connection)

    def executemany(self, user_query: str, values=None, commit=False, close_connection: bool = False):
        self.refresh()
        cursor = self.cursor
        cursor.executemany(user_query, values)
        if commit:
            self.commit(close_connection)

    def commit(self, close_connection: bool = False):
        c = self.connection
        c.ping()
        c.commit()
        if close_connection:
            self.close()
