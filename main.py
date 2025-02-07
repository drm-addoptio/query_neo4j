import os
import re
import time
import functions_framework
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError, ClientError, SessionExpired, ServiceUnavailable 
from flask import jsonify
from utils.nvl_result_transformer import nvl_result_transformer
from logging_config import logger


# Neo4j configuration
URI = os.getenv('NEO4J_URI')
AUTH = (os.getenv('NEO4J_READ_ONLY_USER'), os.getenv('NEO4J_READ_ONLY_PASSWORD'))
DB = os.getenv('NEO4J_DB')  # Assuming a specific database name if needed

# Initialize Neo4j driver
driver = GraphDatabase.driver(uri=URI, auth=AUTH, database=DB)

def execute_neo4j_query(cypher: str, user: str, max_retries=3, retry_delay=2):
    """
    Execute a Cypher query with retry logic to handle session expiration or service unavailability.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            with driver.session(database=DB, impersonated_user=user) as session:
                # Execute the Cypher query
                result = session.run(cypher)
                return [record for record in result]
        except (SessionExpired, ServiceUnavailable) as e:
            # Log the exception and retry
            logger.warning(f"Attempt {attempt + 1}: Session expired or connection lost: {e}")
            time.sleep(retry_delay)  # Wait before retrying
            attempt += 1
        except (DriverError, Neo4jError, ClientError) as e:
            # Handle other errors (e.g., query errors)
            logger.error(f"Cypher query raised an error: {e}")
            raise
    logger.error(f"Max retries reached. Query failed after {max_retries} attempts.")
    raise ServiceUnavailable(f"Failed to execute query after {max_retries} attempts.")

def generate_neo4j_username(email):
    # Replace special characters with underscores
    username = re.sub(r'[^a-zA-Z0-9]', '_', email)
    return username

def add_tenant_conditions_to_query(cypher_query, tenant_id):
    """
    Add tenant-specific label conditions (`d{tenant_id}` or `allAccess`) to the first MATCH clause in a Cypher query.
    """
    tenant_condition_template = "({node_id}:d{tenant_id} OR {node_id}:allAccess)"
    tenant_condition = tenant_condition_template.replace("{tenant_id}", str(tenant_id))

    # Regex to locate the first MATCH clause and extract the first node identifier
    first_match_pattern = r"MATCH\s*\((\w+)(:[^\s\)]*)?\)"  # Match `(n)` or `(n:Label)`

    match = re.search(first_match_pattern, cypher_query, re.IGNORECASE)
    if not match:
        return cypher_query  # If no MATCH clause is found, return the query unchanged

    node_id = match.group(1)  # Extract node identifier, e.g., `n`, `ri`, etc.
    existing_labels = match.group(2) or ""  # Existing labels, if any, e.g., `:Label`

    # Create the tenant condition using the extracted node identifier
    tenant_condition_final = tenant_condition.replace("{node_id}", node_id)

    # If the node already has labels, insert `WHERE` after the labels
    if existing_labels:
        modified_clause = f"MATCH ({node_id}{existing_labels} WHERE {tenant_condition_final})"
    else:
        modified_clause = f"MATCH ({node_id} WHERE {tenant_condition_final})"

    # Replace the original MATCH clause with the modified one
    original_clause = match.group(0)
    modified_query = cypher_query.replace(original_clause, modified_clause, 1)

    return modified_query


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
        #logger.info(f"Request JSON: {request_json}")
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

        user = generate_neo4j_username(user)
        logger.info(f"Transformed email to neo4j username: {user}")

        # Add tenant-specific conditions to the Cypher query
        # Check if the tenant label exists
        if tenant_label_exists(f"d{active_tenant_id}"):
          cypher_query = add_tenant_conditions_to_query(cypher_query, active_tenant_id)
        logger.info(f"Cypher Query: {cypher_query}")

        # Execute the query using the querykb-style approach
        try:
            result_data = querykb(cypher_query, user)
            nvl_data = nvl_result_transformer(result_data)
            #logger.info(f"Transformed data: {nvl_data}")
            json_response = jsonify(nvl_data)
            #logger.info(f"Response: {json_response}")
            # Return the transformed data
            return jsonify(nvl_data), 200, headers
        except Exception as e:
            logger.error('Error executing Cypher query:', e.message)
            return jsonify({'error': e.message}), 500, headers

    except Exception as e:
        logger.error('Error executing Cypher query or fetching credentials:', e)
        return jsonify({'error': 'Internal server error.'}), 500, headers

def tenant_label_exists(tenant_label):
    """
    Check if the tenant-specific label exists in the database.
    """
    query = "CALL db.labels() YIELD label RETURN label"
    try:
        labels = execute_neo4j_query(query, user=None)  # `user=None` for system-level queries
        return tenant_label in [record["label"] for record in labels]
    except ServiceUnavailable as e:
        logger.error(f"Failed to check tenant labels: {e}")
        return False  # Or raise if it's critical


def querykb(cypher: str, user: str) -> list:
    try:
        logger.info(f"Start querying Neo4j with: {cypher}")
        records = execute_neo4j_query(cypher, user)
        logger.info(f"Query completed. Retrieved {len(records)} records.")
        return records
    except ServiceUnavailable as e:
        logger.error(f"Query execution failed: {e}")
        raise
