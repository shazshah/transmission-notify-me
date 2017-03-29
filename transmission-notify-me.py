#author: Shaz
#date: 28/01/2017
#purpose: Check if a torrent has finished downloading and post result to Slack
#version: 1.0.0
#edits: Mark 2

import sqlite3
from sqlite3 import Error
import transmissionrpc
import json #for Slack
import requests #for Slack
import logging #for writing to log
from logging.handlers import RotatingFileHandler #for rotating log file
import configparser #for custom config

#logging.basicConfig(filename="transmission-torrents-log.log", level=logging.INFO, format="%(funcName)s %(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
#log = logging.getLogger("ex")

#---CLASSES---
class Singleton:
    """
    A non-thread-safe helper class to ease implementing singletons.
    This should be used as a decorator -- not a metaclass -- to the
    class that should be a singleton.

    The decorated class can define one `__init__` function that
    takes only the `self` argument. Also, the decorated class cannot be
    inherited from. Other than that, there are no restrictions that apply
    to the decorated class.

    To get the singleton instance, use the `Instance` method. Trying
    to use `__call__` will result in a `TypeError` being raised.

    Shaz: This class is from:
    https://stackoverflow.com/questions/31875/is-there-a-simple-elegant-way-to-define-singletons-in-python

    I need this class because without it the Log_Info class (used for logging) will repeatedly write
    to the log file for every instance of the class being instantiated i.e. the same line appears multiple times.

    The Singleton pattern ensures only one instance of the class is instantiated.
    """

    def __init__(self, decorated):
        self._decorated = decorated

    def Instance(self):
        """
        Returns the singleton instance. Upon its first call, it creates a
        new instance of the decorated class and calls its `__init__` method.
        On all subsequent calls, the already created instance is returned.

        """
        try:
            return self._instance
        except AttributeError:
            self._instance = self._decorated()
            return self._instance

    def __call__(self):
        raise TypeError('Singletons must be accessed through `Instance()`.')

    def __instancecheck__(self, inst):
        return isinstance(inst, self._decorated)

class Config_Settings(object):
    """
    A class to pull configuration settings specified in an
    appropriate txt file (like an ini file).
    """   
    def custom_config(self, config_name, config_value):
        config = configparser.ConfigParser()
        config.read("config.secrets")

        check_config = config.get(config_name, config_value)
        return check_config

@Singleton
class Log_Info(object):
    """
    A class which creates a custom log file in a specified location.
    Uses the @Singleton decorator so it only instantiates once. 
    Without Singleton the log will repeat same lines per instance.
    """
    def __init__(self):
        #configure logging settings
        config = Config_Settings()

        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s', datefmt="%d/%m/%Y %H:%M:%S")

        log_path = config.custom_config("log", "path") #get the log path from the config.secrets

        handler = RotatingFileHandler(log_path, mode='a', maxBytes=200000, backupCount=2, encoding=None, delay=0)

        handler.setFormatter(log_formatter)
        handler.setLevel(logging.INFO)

        self.write_log = logging.getLogger("Logging")
        self.write_log.setLevel(logging.INFO)

        self.write_log.addHandler(handler)

class Slack_Message(object):
    """
    A class to post to specified Slack channel with custom message.
    """
    def post_message_to_channel(self, message):
        logger = Log_Info.Instance()
        config = Config_Settings()

        slack_incoming_webhook = config.custom_config("slack", "webhook")
        slack_incoming_user = config.custom_config("slack", "userid")
        slack_incoming_channel = config.custom_config("slack", "channel")

        payload = {
            "text": message,
            "username": slack_incoming_user,
            "channel": slack_incoming_channel
        }

        logger.write_log.info("Posting to Slack Channel.")
        req = requests.post(slack_incoming_webhook, json.dumps(payload), headers={'content-type': 'application/json'})

class Sql_Database(object):
    """
    Class does several things.
    (1) It will connect to a database or create one if if it does not exist.
    (2) It will create a table with specific fields.
    (3) Add data to those fields.
    (4) Query the database based on set input.
    """
    def connect_to_db(self, db_file):
        logger = Log_Info.Instance()

        try:
            connect_db = sqlite3.connect(db_file)
            logger.write_log.info("Connected to database: " + db_file)
            return connect_db
        except Error as e:
            logger.write_log.exception("Failed to connect to DB. Error: " + e)
            #print(e)

    def close_db(self, db_file):
        logger = Log_Info.Instance()

        logger.write_log.info("Closing database: " + db_file)
        db_file.close()

    def create_table(self, connection, table_to_create):
        logger = Log_Info.Instance()

        try:
            create = connection.cursor()
            create.execute(table_to_create)
            logger.write_log.info("Creating table if it does not exist: " + table_to_create)
        except Error as e:
            logger.write_log.exception("Error creating a table: " + e)
            #print(e)

    def sql_table_structure(self):
        sql_table_structure = """ CREATE TABLE IF NOT EXISTS transmission (
                                primary_id integer PRIMARY KEY,
                                torrent_id integer NOT NULL,
                                torrent_name text NOT NULL,
                                torrent_status text,
                                date_completed text,
                                slack_post_sent text
                        ); """
        return sql_table_structure

    def update_sql_data(self, connection, table_name, new_data):
        logger = Log_Info.Instance()

        sql = ''' INSERT INTO {tn}(torrent_id, torrent_name, torrent_status, date_completed, slack_post_sent)
                    VALUES(?,?,?,?,?) '''.format(tn=table_name)

        current = connection.cursor()
        current.execute(sql, new_data)
        logger.write_log.info("Adding torrent to Database.")
        #print(current.lastrowid)

    def query_database(self, connection, table_name, column_name1, column_name2, torrent_id):
        logger = Log_Info.Instance()

        sql = ''' SELECT {cn1}, {cn2} FROM {tn} WHERE {cn1} = {tid} '''.format(cn1=column_name1, cn2=column_name2, tn=table_name, tid=torrent_id)
        current = connection.cursor()
        current.execute(sql)
        found_rows = current.fetchall()
        if not found_rows:
            #list is empty so not in DB already
            logger.write_log.info("Torrent is not already in Database. Adding. Torrent ID: " + str(torrent_id))
            return False
        else:
            #list is NOT empty so must be in DB already
            logger.write_log.info("Torrent is already in Database. Nothing to do. Torrent ID: " + str(torrent_id))
            return True

class Transmission_Downloads(object):
    """
    A class which does several things:
    (1) Connect to transmission client with specific credentials.
    (2) Query the client i.e. what torrent is currently in the client.
    (3) Extricate torrent info which will be added to the database.
    """
    def connect_transmission(self, server, port_number, username, passwd):
        logger = Log_Info.Instance()

        try:
            client_credentials = transmissionrpc.Client(server, port=port_number, user=username, password=passwd)
            logger.write_log.info("Connected to Tranmissions using supplied credentials.")
            return client_credentials
        except Exception as e:
            logger.write_log.exception("Unable to connect to Transmission using supplied credentials. Terminating script. This the error: " + str(e))
            #print(e)
            exit()

    def get_torrent_info(self, connection):
         logger = Log_Info.Instance()

         torrents = connection.get_torrents()
         for torrent in torrents:
            logger.write_log.info("Getting torrent info from Transmission... Torrent ID: " + str(torrent.id) + " Torrent Name: " + str(torrent.name))
            torrent.update()
            if torrent.status == 'seeding' or torrent.isFinished == True:
                logger.write_log.info("Found a torrent which is complete: " + str(torrent.name))
                temp_date_done = torrent.date_done.strftime("%d/%m/%Y")
                torrent_info = (int(torrent.id), str(torrent.name), str(torrent.status), str(temp_date_done))
                yield torrent_info #using yield instead of return because return will terminate the function after first iteration

            else:
                logger.write_log.warning("Torrent is incomplete or paused, ignoring: " + str(torrent.name))

    def add_torrent_to_database(self, torrent_info, db_file_name):
        logger = Log_Info.Instance()

        query_torrent_id = torrent_info[0] #torrent_id is first item in list
        sql_database = Sql_Database()
        sql_connection = sql_database.connect_to_db(db_file_name)

        slack = Slack_Message()
        with sql_connection:
            #check if torrent_id is already in DB, if yes then then nothing to do, if None then need to add DB.
            logger.write_log.info("Checking if torrent is already in Database meaning a Slack Message has been sent in the past.")
            already_in_sql = sql_database.query_database(sql_connection, "transmission", "torrent_id", "torrent_name", query_torrent_id)
            if already_in_sql == False:
                torrent_info = torrent_info + ("yes",) #add yes to the torrent_info tuple to indicate slack post has been sent.
                table_name = "transmission"
                sql_database.update_sql_data(sql_connection, table_name, torrent_info)
                #send the slack post
                slack.post_message_to_channel("Downloaded torrent: " + torrent_info[1])
            else:
                #tid already in db
                return None
def main():
    config = Config_Settings()

    #---- SQL SECTION ----

    #get the database path from the config file
    db_path = config.custom_config("database", "databasepath") #db file automatically creates if not present.

    sql_database = Sql_Database()

    #make a connection to the db
    sql_connection = sql_database.connect_to_db(db_path)
    

    #get the table structure
    table_structure = sql_database.sql_table_structure()

    if sql_connection is not None:
        #create the table with the required table structure if it does not already exist
        sql_database.create_table(sql_connection,table_structure)
    
        #close the db
        sql_database.close_db
    else:
        print("Error! Unable to establish DB connection.")

    #---- TRANSMISSION SECTION ----

    #get transmission client connection info from config file
    transmission_server = config.custom_config("transmission", "server")
    transmission_port = config.custom_config("transmission", "port")
    transmission_username = config.custom_config("transmission", "username")
    transmission_password = config.custom_config("transmission", "password")

    transmission_downloads = Transmission_Downloads()

    #connect to transmission
    transmission_connection = transmission_downloads.connect_transmission(transmission_server, transmission_port, transmission_username, transmission_password)

    #get torrent info for any torrents successfully downloaded
    transmission_torrent_info = transmission_downloads.get_torrent_info(transmission_connection) #this will give a generator yield

    #check if torrents are in DB, if not in DB, add to DB and then send a slack message
    for torrent in transmission_torrent_info:
        transmission_torrent_in_db = transmission_downloads.add_torrent_to_database(torrent, db_path)

#Run script
main()