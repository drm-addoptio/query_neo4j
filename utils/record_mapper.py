from config.styles_config import label_style_config, relationship_style_config  # Adjust the import path as needed
from neo4j.time import DateTime, Date
from neo4j.graph import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# Function to handle DateTime conversion
def convert_to_serializable(value):
    if isinstance(value, (DateTime, Date)):
        return value.iso_format()
    return value

# Function to exclude specific properties
def filter_properties(properties, excluded_keys):
    """
    Filters out excluded keys from the properties dictionary.
    """
    return {k: v for k, v in properties.items() if k not in excluded_keys}

def process_key(key, record):
    """
    Process a single key in the record to generate node/relationship data.
    """
    element = record.get(key)
    if element is None:
        return None
    
    # Properties to exclude
    excluded_properties = {"embedding", "type"}  # Ensure "type" is never overwritten

    # Handle paths
    if isinstance(element, Path):  
        path_data = {"type": "path", "nodes": [], "relationships": []}

        for node in element.nodes:
            labels = list(node.labels)
            filtered_labels = [label for label in labels if label != 'allAccess']
            primary_label = filtered_labels[0] if filtered_labels else "unknown"
            label_config = label_style_config.get(primary_label, {})

            path_data["nodes"].append({
                "type": "node",
                "id": node.element_id,
                "captions": [{
                    "value": node.get("classification", primary_label),
                    "styles": label_config.get("styles", ["bold"])
                }],
                "size": label_config.get("size", 30),
                "color": label_config.get("color", "gray"),
                **{k: convert_to_serializable(v) for k, v in filter_properties(node._properties, excluded_properties).items()},
                "labels": labels,  
            })

        for relationship in element.relationships:
            relationship_config = relationship_style_config.get(relationship.type, {})

            path_data["relationships"].append({
                "type": "relationship",
                "relationshipType": relationship.type,
                "id": relationship.element_id,
                "from": relationship.start_node.element_id,
                "to": relationship.end_node.element_id,
                "captions": [{
                    "value": relationship_config.get("caption", "missing caption"),
                    "styles": ["bold"]
                }],
                "color": "gray",
                **{k: convert_to_serializable(v) for k, v in filter_properties(relationship._properties, excluded_properties).items()},
            })
        return path_data

    # Handle nodes
    if hasattr(element, 'labels'):
        labels = list(element.labels)
        filtered_labels = [label for label in labels if label != 'allAccess']
        primary_label = filtered_labels[0] if filtered_labels else "unknown"
        label_config = label_style_config.get(primary_label, {}) if primary_label else {}
        
        return {
            "type": "node",  # Ensure "type" is always "node"
            "id": element.element_id,
            "captions": [{
                "value": element.get("classification", primary_label),
                "styles": label_config.get("styles", ["bold"])
            }],
            "size": label_config.get("size", 30),
            "color": label_config.get("color", "gray"),
            **{k: convert_to_serializable(v) for k, v in filter_properties(element._properties, excluded_properties).items()},
            "labels": labels,
        }

    # Handle relationships with nodes
    if hasattr(element, 'nodes') and isinstance(element.nodes, (list, tuple)) and len(element.nodes) == 2:
        start_node, end_node = element.nodes
        relationship_config = relationship_style_config.get(element.type, {})

        return {
            "type": "relationship",
            "relationshipType": element.type,
            "id": element.element_id,
            "from": start_node.element_id,
            "to": end_node.element_id,
            "captions": [{
                "value": relationship_config.get("caption", "missing caption"),
                "styles": ["bold"]
            }],
            "color": "gray",
            **{k: convert_to_serializable(v) for k, v in filter_properties(element._properties, excluded_properties).items()},
        }

    # Handle relationships without nodes
    if hasattr(element, 'type'):
        relationship_config = relationship_style_config.get(element.type, {})

        return {
            "type": "relationship",
            "relationshipType": element.type,
            "id": element.element_id,
            "from": element.start_node.id,
            "to": element.end_node.id,
            "captions": [{
                "value": relationship_config.get("caption", "missing caption"),
                "styles": relationship_config.get("styles", ["bold"])
            }],
            "color": relationship_config.get("color", "gray"),
            **{k: convert_to_serializable(v) for k, v in filter_properties(element._properties, excluded_properties).items()},
        }

    return None

def record_mapper_parallel(record, num_workers=4):
    """
    Parallelize key-level processing within a single record, with a limit on the number of keys processed.
    """
    elements = []

    # Slice the keys to enforce the limit
    keys_to_process = list(record.keys())
    # Use a thread pool for parallel processing
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_key, key, record): key for key in keys_to_process}

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:  # Only append if processing the key returned valid data
                    elements.append(result)
            except Exception as e:
                print(f"Error processing key {futures[future]}: {e}")

    return elements

