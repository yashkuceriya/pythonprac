import pyarrow.parquet as pq
import pandas as pd
from neo4j import GraphDatabase
import time


class DataLoader:

    def __init__(self, uri, user, password):
        """
        Connect to the Neo4j database and other init steps
        
        Args:
            uri (str): URI of the Neo4j database
            user (str): Username of the Neo4j database
            password (str): Password of the Neo4j database
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password), encrypted=False)
        self.driver.verify_connectivity()


    def close(self):
        """
        Close the connection to the Neo4j database
        """
        self.driver.close()


    # Define a function to create nodes and relationships in the graph
    def load_transform_file(self, file_path):
        """
        Load the parquet file and transform it into a csv file
        Then load the csv file into neo4j

        Args:
            file_path (str): Path to the parquet file to be loaded
        """

        # Read the parquet file
        trips = pq.read_table(file_path)
        trips = trips.to_pandas()

        # Some data cleaning and filtering
        trips = trips[['tpep_pickup_datetime', 'tpep_dropoff_datetime', 'PULocationID', 'DOLocationID', 'trip_distance', 'fare_amount']]

        # Filter out trips that are not in bronx
        bronx = [3, 18, 20, 31, 32, 46, 47, 51, 58, 59, 60, 69, 78, 81, 94, 119, 126, 136, 147, 159, 167, 168, 169, 174, 182, 183, 184, 185, 199, 200, 208, 212, 213, 220, 235, 240, 241, 242, 247, 248, 250, 254, 259]
        trips = trips[trips.iloc[:, 2].isin(bronx) & trips.iloc[:, 3].isin(bronx)]
        trips = trips[trips['trip_distance'] > 0.1]
        trips = trips[trips['fare_amount'] > 2.5]

        # Convert date-time columns to supported format
        trips['tpep_pickup_datetime'] = pd.to_datetime(trips['tpep_pickup_datetime'], format='%Y-%m-%d %H:%M:%S')
        trips['tpep_dropoff_datetime'] = pd.to_datetime(trips['tpep_dropoff_datetime'], format='%Y-%m-%d %H:%M:%S')
        
        # Convert to csv and store in the current directory
        save_loc = "/var/lib/neo4j/import/" + file_path.split(".")[0] + '.csv'
        trips.to_csv(save_loc, index=False)

        # Insert the nodes and relationships into Neo4j
        with self.driver.session() as session:
            for index, row in trips.iterrows():
                # Create nodes for PULocationID and DOLocationID
                query_create_pulocation = (
                    "MERGE (p:Location {name: $PULocationID})"
                )
                query_create_dolocation = (
                    "MERGE (d:Location {name: $DOLocationID})"
                )
                
                # Create the relationship between the Pickup and Dropoff locations
                query_create_trip = (
                    "MATCH (p:Location {name: $PULocationID}), (d:Location {name: $DOLocationID}) "
                    "CREATE (p)-[r:TRIP {"
                    "distance: $trip_distance, "
                    "fare: $fare_amount, "
                    "pickup_dt: $pickup_datetime, "
                    "dropoff_dt: $dropoff_datetime"
                    "}]->(d)"
                )
                
                # Run the queries to insert the nodes and the relationship
                session.run(query_create_pulocation, PULocationID=row['PULocationID'])
                session.run(query_create_dolocation, DOLocationID=row['DOLocationID'])
                session.run(query_create_trip,
                            PULocationID=row['PULocationID'],
                            DOLocationID=row['DOLocationID'],
                            trip_distance=row['trip_distance'],
                            fare_amount=row['fare_amount'],
                            pickup_datetime=row['tpep_pickup_datetime'],
                            dropoff_datetime=row['tpep_dropoff_datetime'])

            print(f"Data with nodes and relationships loaded successfully into Neo4j from {file_path}")


def main():

    total_attempts = 10
    attempt = 0

    # The database takes some time to starup!
    # Try to connect to the database 10 times
    while attempt < total_attempts:
        try:
            data_loader = DataLoader("neo4j://localhost:7687", "neo4j", "test123")
            data_loader.load_transform_file("yellow_tripdata_2022-03.parquet")
            data_loader.close()
            
            attempt = total_attempts

        except Exception as e:
            print(f"(Attempt {attempt+1}/{total_attempts}) Error: ", e)
            attempt += 1
            time.sleep(10)


if __name__ == "__main__":
    main()

