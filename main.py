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

def add_tenant_condition(cypher_query, tenant_id):
    """
    Add the tenant_id condition to the Cypher query at the correct position.
    
    - If the query has a `WHERE` clause, the condition is appended using 'AND'.
    - If no `WHERE` clause exists, the condition is inserted after the first `MATCH` or `OPTIONAL MATCH` clause, but outside the brackets.
    """
    cypher_query = cypher_query.strip()  # Clean up any surrounding whitespace
    
    # Check if the query contains an existing WHERE clause
    if "WHERE" in cypher_query.upper():
        # Append the tenant condition to the existing WHERE clause using AND
        where_pos = cypher_query.upper().find("WHERE")  # Find the WHERE keyword
        cypher_query = cypher_query[:where_pos + len("WHERE")] + " " + f"tenant_id = '{tenant_id}'" + cypher_query[where_pos + len("WHERE"):]

    else:
        # No WHERE clause found, add after MATCH or OPTIONAL MATCH
        if "MATCH" in cypher_query.upper() or "OPTIONAL MATCH" in cypher_query.upper():
            match_pos = cypher_query.upper().find("MATCH")  # Find the first MATCH
            if match_pos != -1:
                # Add the WHERE clause right after MATCH, but outside any brackets
                cypher_query = cypher_query[:match_pos + len("MATCH")] + f" WHERE tenant_id = '{tenant_id}' " + cypher_query[match_pos + len("MATCH"):]

    return cypher_query


@functions_framework.http
def main(request):
    # Set CORS headers
    # This is important for browser clients. If not present we will receive cors errors on the browser
    headers = {
        'Access-Control-Allow-Origin': request.headers.get('Origin'),
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Methods': 'POST',
        'Access-Control-Allow-Headers': 'Content-Type'
    }

    # Handle OPTIONS preflight requests
    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        logger.info("Running Cloud Function...")

        # Validate credentials
        if not URI or not AUTH[0] or not AUTH[1]:
            return jsonify({'error': 'Neo4j credentials are missing from environment variables.'}), 400, headers

        # Get the Cypher query from the request body
        request_json = request.get_json()
        logger.info(f"Request JSON: {request_json}")
        cypher_query = request_json.get('query') if request_json else None
        logger.info(f"Cypher Query: {cypher_query}")

        # Get the supabase user email from the request header "x-supabase-user"
        user = request.headers.get('x-supabase-user')
        logger.info(f"User: {user}")

        # Get the active tenant id from the request header "x-active-tenant-id"
        active_tenant_id = request.headers.get('x-active-tenant-id')
        logger.info(f"active_tenant_id: {active_tenant_id}")

        if not cypher_query:
            return jsonify({'error': 'Cypher query is required.'}), 400, headers
        
        if not user:
            return jsonify({'error': 'User is required.'}), 400, headers
        
        if not active_tenant_id:
            return jsonify({'error': 'Active tenant id is required.'}), 400, headers

        cypher_query = add_tenant_condition(cypher_query, active_tenant_id)
        logger.info(f"Updated Cypher Query: {cypher_query}")

        # Execute the query using the querykb-style approach
        try:
            result_data = querykb(cypher_query, user, active_tenant_id)
            nvl_data = nvl_result_transformer(result_data)
            logger.info(f"Transformed data: {nvl_data}")
            json_response = jsonify(nvl_data)
            logger.info(f"Response: {json_response}")
            # Return the transformed data
            return jsonify(nvl_data), 200, headers
        except Exception as e:
            logger.error('Error executing Cypher query:', e)
            return jsonify({'error': 'Error executing Cypher query.'}), 500, headers

    except Exception as e:
        logger.error('Error executing Cypher query or fetching credentials:', e)
        return jsonify({'error': 'Internal server error.'}), 500, headers


def querykb(cypher: str, user: str, active_tenant_id: str) -> list:
    try:
        with GraphDatabase.driver(uri=URI, auth=AUTH, warn_notification_severity="WARNING") as driver:
            driver.verify_connectivity()
            logger.info(f"Start querying Neo4j with: {cypher}")

            # Execute the Cypher query
            records, summary, keys = driver.execute_query(
                cypher,
                database_=DB,
                impersonated_user_=user
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
