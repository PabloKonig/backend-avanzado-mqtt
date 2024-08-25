from datetime import datetime, timedelta, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os

# Configuración de InfluxDB
influxdb_config = {
    "url": os.environ.get("INFLUXDB_URL"),      # Url de InfluxDB
    "token": os.environ.get("INFLUXDB_TOKEN"),    # Token de InfluxDB
    "org": os.environ.get("INFLUXDB_ORG"),      # Organización de InfluxDB
    "bucket": os.environ.get("INFLUXDB_BUCKET")    # Nombre del bucket
}

# Función para guardar datos en InfluxDB
def save_to_influxdb(measurement, value):
    with InfluxDBClient(url=influxdb_config["url"], token=influxdb_config["token"], org=influxdb_config["org"]) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        point = Point(measurement).field("value", value).time(datetime.now(datetime.UTC), WritePrecision.NS)
        write_api.write(influxdb_config["bucket"], influxdb_config["org"], point)

# Función para obtener datos de las últimas 24 hs.
def dataDB_24_hs(measurement):
    tiempo_actual = datetime.now(timezone.utc)
    tiempo_hace_24_horas = tiempo_actual - timedelta(hours=24)

    query = (
    'from(bucket: "' + influxdb_config["bucket"] + '")'
    ' |> range(start: ' + tiempo_hace_24_horas.isoformat() + ', stop: ' + tiempo_actual.isoformat() + ')'
    ' |> filter(fn: (r) => r["_measurement"] == "' + measurement + '")'
    ' |> filter(fn: (r) => r["_field"] == "value")'
    ' |> aggregateWindow(every: 10m, fn: mean, createEmpty: false)'
    ' |> yield(name: "mean")'
    )  # Últimas 24 hs.  # measurement (temperatura o presión) # Solo tomamos un punto de medición cada 10 minutos.

    with InfluxDBClient(url=influxdb_config["url"], token=influxdb_config["token"], org=influxdb_config["org"]) as client2:
        result = client2.query_api().query(org=influxdb_config["org"], query=query)
    #print(json.dumps(result.to_json(), indent=4))  # Imprime el resultado en formato JSON
    # Procesa los resultados
    data = []
    for table in result:
        for record in table.records:
            tiempo = record.values.get("_time").strftime("%d-%m-%Y %H:%M:%S")
            valor = round(record.values.get("_value"), 2)
            data.append({
                "tiempo": tiempo,
                "valor": valor
            })
    return data       