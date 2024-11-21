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

def add_tenant_label_to_match(cypher_query, tenant_id):
    """
    Add the tenant_id as a second label to all nodes in the MATCH clause.
    
    - Each node will be matched with its original label and the tenant label.
    - The tenant label is dynamically generated as 't{tenant_id}' (e.g., 't12').
    """
    tenant_label = f"t{tenant_id}"  # e.g., 't12' for tenant_id = 12
    
    # Split the query by lines for easier processing
    query_lines = cypher_query.splitlines()
    
    modified_query = []
    
    for line in query_lines:
        # Look for MATCH clauses and modify the nodes being matched
        if "MATCH" in line.upper():
            # We want to add the tenant label after each node label
            modified_line = line
            # For each node label in the MATCH clause, add the tenant label
            modified_line = modified_line.replace(")", f":{tenant_label})")
            modified_query.append(modified_line)
        else:
            # Leave other lines unchanged
            modified_query.append(line)
    
    return "\n".join(modified_query)



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

        cypher_query = add_tenant_label_to_match(cypher_query, active_tenant_id)
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
