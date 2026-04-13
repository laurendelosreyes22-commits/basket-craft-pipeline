import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_URL = (
    "mysql+pymysql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        host=os.environ["MYSQL_HOST"],
        port=os.environ["MYSQL_PORT"],
        db=os.environ["MYSQL_DATABASE"],
    )
)

POSTGRES_URL = (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        db=os.environ["POSTGRES_DB"],
    )
)
