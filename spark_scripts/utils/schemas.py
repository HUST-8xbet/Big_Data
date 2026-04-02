from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

BINANCE_SCHEMA = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True),
    StructField("timestamp", LongType(), True)
])
