from config.styles_config import label_style_config, relationship_style_config  # Adjust the import path as needed
from neo4j.time import DateTime, Date

# Function to handle DateTime conversion
def convert_to_serializable(value):
    if isinstance(value, (DateTime, Date)):
        return value.iso_format()
    return value

def record_mapper(record):
    elements = []
    for key in record.keys():
        element = record.get(key)
        print(f"Element: {element}")

        # Handle nodes
        if element and hasattr(element, 'labels'):
            # Convert frozenset to list and access the first label
            labels = list(element.labels)
            label_config = label_style_config.get(labels[0], {}) if labels else {}

            # Format the node with styles, captions, and other properties
            node_data = {
                "type": "node",
                "id": element.element_id,  # Unique ID for each node
                "captions": [
                    {
                        "value": element.get("classification", labels[0]),
                        "styles": label_config.get("styles", ["bold"])
                    }
                ],
                "size": label_config.get("size", 30),  # Default size if not defined
                "color": label_config.get("color", "gray"),  # Default color if not defined
                **{k: convert_to_serializable(v) for k, v in element._properties.items()},  # Convert DateTime properties
                "labels": labels,  # Keep labels of the node
            }
            elements.append(node_data)
        
        # Handle relationships
        else:
            # Retrieve configuration for the relationship type
            relationship_config = relationship_style_config.get(element.type, {})

            # Format the relationship with styles, captions, and other properties
            relationship_data = {
                "type": "relationship",
                "relationshipType": element.type,
                "id": element.element_id,  # Unique ID for each relationship
                "from": element.start_node.id,  # ID of the starting node
                "to": element.end_node.id,  # ID of the ending node
                "captions": [
                    {
                        "value": relationship_config.get("caption", "missing caption"),
                        "styles": relationship_config.get("styles", ["bold"])
                    }
                ],
                "color": relationship_config.get("color", "gray"),  # Default color if not defined
                **{k: convert_to_serializable(v) for k, v in element._properties.items()},  # Convert DateTime properties
            }
            elements.append(relationship_data)

    return elements  # Return list of formatted nodes and relationships
