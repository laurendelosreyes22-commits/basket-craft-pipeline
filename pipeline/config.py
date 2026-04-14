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
        user=os.environ.get("POSTGRES_USER", os.environ.get("PG_USER", "")),
        password=os.environ.get("POSTGRES_PASSWORD", os.environ.get("PG_PASSWORD", "")),
        host=os.environ.get("POSTGRES_HOST", os.environ.get("PG_HOST", "localhost")),
        port=os.environ.get("POSTGRES_PORT", os.environ.get("PG_PORT", "5432")),
        db=os.environ.get("POSTGRES_DB", os.environ.get("PG_DB", "")),
    )
)

RDS_URL = (
    "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ["RDS_USER"],
        password=os.environ["RDS_PASSWORD"],
        host=os.environ["RDS_HOST"],
        port=os.environ["RDS_PORT"],
        db=os.environ["RDS_DATABASE"],
    )
)
