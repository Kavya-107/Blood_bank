import sqlite3

class Database:
    """Database connection manager class"""
    __connection_pool = None
    
    @classmethod
    def initialize(cls):
        """Initialize the database connection pool"""
        cls.__connection_pool = sqlite3.connect('blood_bank.db', check_same_thread=False)
        
        # Create tables if they don't exist
        with cls.__connection_pool as connection:
            cursor = connection.cursor()
            
            # Create donors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS donors (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    blood_type TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    last_donation_date TEXT
                )
            ''')
            
            # Create recipients table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recipients (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    blood_type TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    medical_condition TEXT,
                    last_request_date TEXT
                )
            ''')
            
            # Create blood_bank table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blood_bank (
                    id INTEGER PRIMARY KEY,
                    blood_type TEXT NOT NULL,
                    quantity_ml INTEGER NOT NULL,
                    donor_id INTEGER,
                    collection_date TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    FOREIGN KEY (donor_id) REFERENCES donors (id)
                )
            ''')
            
            # Create blood_requests table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blood_requests (
                    id INTEGER PRIMARY KEY,
                    blood_type TEXT NOT NULL,
                    quantity_ml INTEGER NOT NULL,
                    recipient_id INTEGER,
                    request_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (recipient_id) REFERENCES recipients (id)
                )
            ''')

    @classmethod
    def get_connection(cls):
        """Get a connection from the pool"""
        if cls.__connection_pool is None:
            cls.initialize()
        return cls.__connection_pool

class CursorFromConnectionPool:
    """Context manager for database cursors"""
    def __init__(self):
        self.connection = None
        self.cursor = None

    def __enter__(self):
        self.connection = Database.get_connection()
        self.cursor = self.connection.cursor()
        return self.cursor

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if exception_value:  # If there was an exception
            self.connection.rollback()
        else:
            self.connection.commit()
        
        # Don't close the connection, as we're reusing it in a pool
        if self.cursor:
            self.cursor.close()