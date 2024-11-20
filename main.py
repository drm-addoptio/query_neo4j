import os
import functions_framework
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from flask import jsonify
from utils.nvl_result_transformer import nvl_result_transformer
from logging_config import logger

# Neo4j configuration
URI = os.getenv('NEO4J_URI')
AUTH = (os.getenv('NEO4J_READ_ONLY_USER'), os.getenv('NEO4J_READ_ONLY_PASSWORD'))
DB = os.getenv('NEO4J_DB')  # Assuming a specific database name if needed

@functions_framework.http
def main(request):
    try:
        logger.info("Running Cloud Function...")

        # Validate credentials
        if not URI or not AUTH[0] or not AUTH[1]:
            return jsonify({'error': 'Neo4j credentials are missing from environment variables.'}), 400, headers

        # Get the Cypher query from the request body
        request_json = request.get_json()
        logger.info(f"Request JSON: {request_json}")
        logger.info(f"Request Headers: {request.headers}")
        cypher_query = request_json.get('query') if request_json else None
        logger.info(f"Cypher Query: {cypher_query}")

        if not cypher_query:
            return jsonify({'error': 'Cypher query is required.'}), 400

        # Execute the query using the querykb-style approach
        try:
            result_data = querykb(cypher_query)
            nvl_data = nvl_result_transformer(result_data)
            logger.info(f"Transformed data: {nvl_data}")
            json_response = jsonify(nvl_data)
            logger.info(f"Response: {json_response}")
            # Return the transformed data
            return jsonify(nvl_data), 200
        except Exception as e:
            logger.error('Error executing Cypher query:', e)
            return jsonify({'error': 'Error executing Cypher query.'}), 500

    except Exception as e:
        logger.error('Error executing Cypher query or fetching credentials:', e)
        return jsonify({'error': 'Internal server error.'}), 500

def querykb(cypher: str) -> list:
    try:
        with GraphDatabase.driver(uri=URI, auth=AUTH, warn_notification_severity="WARNING") as driver:
            driver.verify_connectivity()
            logger.info(f"Start querying Neo4j with: {cypher}")

            # Execute the Cypher query
            records, summary, keys = driver.execute_query(
                cypher,
                database_=DB,
                impersonated_user_="user1212"
            )
            
            # Handle any notifications or warnings
            if summary.notifications and len(summary.notifications) > 0:
                raise Neo4jError(summary.notifications[0], cypher)

            logger.info(f"Query completed in {summary.result_available_after} ms")
            logger.info(f"Results: {records}")

            # Return records in a format suitable for transformation
            return records

    except (DriverError, Neo4jError) as e:
        logger.error(f"Cypher query raised an error: {e}")
        raise
