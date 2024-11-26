from config.styles_config import label_style_config, relationship_style_config  # Adjust the import path as needed
from neo4j.time import DateTime, Date
from concurrent.futures import ThreadPoolExecutor, as_completed


# Function to handle DateTime conversion
def convert_to_serializable(value):
    if isinstance(value, (DateTime, Date)):
        return value.iso_format()
    return value

def process_key(key, record):
    """
    Process a single key in the record to generate node/relationship data.
    """
    element = record.get(key)
    if element is None:
        return None

    # Handle nodes
    if hasattr(element, 'labels'):  # It's a node
        labels = list(element.labels)
        label_config = label_style_config.get(labels[0], {}) if labels else {}

        return {
            "type": "node",
            "id": element.element_id,
            "captions": [{
                "value": element.get("classification", labels[0]),
                "styles": label_config.get("styles", ["bold"])
            }],
            "size": label_config.get("size", 30),
            "color": label_config.get("color", "gray"),
            **{k: convert_to_serializable(v) for k, v in element._properties.items()},
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
            **{k: convert_to_serializable(v) for k, v in element._properties.items()},
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
            **{k: convert_to_serializable(v) for k, v in element._properties.items()},
        }

    return None

def record_mapper_parallel(record, num_workers=4):
    """
    Parallelize key-level processing within a single record.
    """
    elements = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_key, key, record): key for key in record.keys()}

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:  # Only append if processing the key returned valid data
                    elements.append(result)
            except Exception as e:
                print(f"Error processing key {futures[future]}: {e}")

    return elements

def record_mapper(record):
    # Instead of appending one element at a time, we'll use list comprehensions for efficiency
    # Create the elements list in advance
    elements = []

    for key, element in record.items():
        if element is None:
            continue  # Skip if the element is None
        
        # Check if the element has 'nodes' or 'type' and process accordingly
        is_node = hasattr(element, 'labels')
        is_relationship_with_nodes = hasattr(element, 'nodes') and isinstance(element.nodes, (list, tuple)) and len(element.nodes) == 2
        is_relationship_without_nodes = hasattr(element, 'type') and not is_relationship_with_nodes

        if is_node:
            # Process node elements
            labels = list(element.labels) if element.labels else []
            label_config = label_style_config.get(labels[0], {}) if labels else {}

            node_data = {
                "type": "node",
                "id": element.element_id,
                "captions": [{
                    "value": element.get("classification", labels[0]),
                    "styles": label_config.get("styles", ["bold"])
                }],
                "size": label_config.get("size", 30),
                "color": label_config.get("color", "gray"),
                **{k: convert_to_serializable(v) for k, v in element._properties.items()},
                "labels": labels,
            }
            elements.append(node_data)

        elif is_relationship_with_nodes:
            # Process relationship elements with nodes
            start_node, end_node = element.nodes

            relationship_config = relationship_style_config.get(element.type, {})

            relationship_data = {
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
                **{k: convert_to_serializable(v) for k, v in element._properties.items()},
            }
            elements.append(relationship_data)

        elif is_relationship_without_nodes:
            # Process relationship elements without nodes
            relationship_config = relationship_style_config.get(element.type, {})

            relationship_data = {
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
                **{k: convert_to_serializable(v) for k, v in element._properties.items()},
            }
            elements.append(relationship_data)

    return elements

