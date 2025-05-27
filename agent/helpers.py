from typing import TypedDict, Any, List, Dict
import os
import datetime
from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient
from pymongo.results import InsertOneResult
import requests
import logging
from pymongo.errors import PyMongoError


_ = load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MONGO_URI: str | None = os.getenv("MONGODB_URI") 
MONGO_URI = os.getenv("MONGODB_URI")  # Remove type annotation   
if not MONGO_URI:
    logger.error("MONGODB_URI environment variable is not set")
    raise ValueError("MONGODB_URI environment variable is not set")

try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    logger.info("Successfully connected to MongoDB")
    
    db = client['patient_companion_assistant']
    callers_collection = db['callers']
    symptoms_collection = db['symptoms']
    appointments_collection = db['appointments']
    temperature_collection = db['temperature']
    images_collection = db['user_images']
    pain_collection = db['pain']
    text_collection = db['texts']

except PyMongoError as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

class User(TypedDict):
    phone_number: str
    name: str

class Symptom(TypedDict):
    symptom: str
    phone_number: str
    timestamp: datetime.datetime

def save_user(user: User) -> bool:
    try:
        result: InsertOneResult = callers_collection.insert_one(document=user)
        if result.inserted_id:
            logger.info(f"User saved successfully: {user['phone_number']}")
            return True
        else:
            logger.warning(f"Failed to save user: {user['phone_number']}")
            return False
    except PyMongoError as e:
        logger.error(f"MongoDB error while saving user: {e}")
        return False
    
def update_user_name(phone_number: str, name: str) -> bool:
    """
    Updates the name of an existing user identified by phone_number.
    
    Args:
        phone_number (str): The phone number of the user to update
        name (str): The new name to save for the user
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Log the operation for debugging
        print(f"update_user_name called with phone_number: '{phone_number}', name: '{name}'")
        
        # Verify MongoDB connection is still alive
        try:
            client.admin.command('ping')
            print("MongoDB connection is alive")
        except Exception as e:
            print(f"MongoDB connection test failed: {e}")
            return False
        
        # Verify the collection exists
        db_list = client.list_database_names()
        print(f"Available databases: {db_list}")
        
        if 'patient_companion_assistant' in db_list:
            collections = db['patient_companion_assistant'].list_collection_names()
            print(f"Collections in patient_companion_assistant: {collections}")
        
        # Check if user exists before attempting update
        existing_user = callers_collection.find_one({"phone_number": phone_number})
        print(f"Existing user before update: {existing_user}")
        
        # Find and update the user document
        print(f"Executing update_one with filter: {{'phone_number': '{phone_number}'}} and update: {{'$set': {{'name': '{name}'}}}}")
        
        result = callers_collection.update_one(
            {"phone_number": phone_number},
            {"$set": {"name": name}}
        )
        
        # Log the update result
        print(f"update_one result - matched_count: {result.matched_count}, modified_count: {result.modified_count}")
        
        # Check if the update was successful
        if result.matched_count > 0:
            print(f"Match found for phone_number: {phone_number}")
            
            if result.modified_count > 0:
                print(f"Document was modified with new name: {name}")
            else:
                print(f"Document matched but no changes were needed (name may already be '{name}')")
                
            # Verify the update by retrieving the user again
            updated_user = callers_collection.find_one({"phone_number": phone_number})
            print(f"User document after update: {updated_user}")
            
            return True
        else:
            print(f"No user found with phone_number: {phone_number}")
            return False
            
    except Exception as e:
        import traceback
        print(f"Exception in update_user_name: {str(e)}")
        print(traceback.format_exc())
        return False

def get_user_from_db(phone_number: str) -> User | None:
    try:
        last_doc: Any | None = callers_collection.find_one(filter={"phone_number": phone_number}, sort=[("_id", DESCENDING)])
        if last_doc:
            logger.info(f"User found: {phone_number}")
            return last_doc
        else:
            logger.info(f"User not found: {phone_number}")
            return None
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving user: {e}")
        return None

def save_symptom(symptom: str, phone_number: str = None) -> bool:
    try:
        logger.info(f"Attempting to save symptom: {symptom} for user: {phone_number}")
        if not symptom or not isinstance(symptom, str):
            logger.warning(f"Invalid symptom format: {symptom}")
            return False
            
        document = {
            "symptom": symptom,
            "phone_number": phone_number,
            "timestamp": datetime.datetime.now()
        }
        logger.info(f"Inserting document: {document}")
        
        result = symptoms_collection.insert_one(document)
        if result.inserted_id:
            logger.info(f"Symptom saved successfully with ID: {result.inserted_id}")
            return True
        else:
            logger.warning("Failed to save symptom, no inserted_id returned")
            return False
    except PyMongoError as e:
        logger.error(f"MongoDB error while saving symptom: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while saving symptom: {e}")
        return False

# added for temp checking
def save_temp(temperature: float, phone_number: str = None) -> bool:
    try:
        logger.info(f"Attempting to save temperature: {temperature} for user: {phone_number}")
        if not isinstance(temperature, (int, float)):
            logger.warning(f"Invalid temperature format: {temperature}")
            return False
            
        document = {
            "temperature": temperature,
            "phone_number": phone_number,
            "timestamp": datetime.datetime.now()
        }
        logger.info(f"Inserting document: {document}")
        
        result = temperature_collection.insert_one(document)
        if result.inserted_id:
            logger.info(f"Temperature saved successfully with ID: {result.inserted_id}")
            return True
        else:
            logger.warning("Failed to save Temperature, no inserted_id returned")
            return False
    except PyMongoError as e:
        logger.error(f"MongoDB error while saving Temperature: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while saving Temperature: {e}")
        return False


def get_symptom_from_db() -> str:
    try:
        last_symp_doc = symptoms_collection.find_one(sort=[("_id", DESCENDING)])
        if last_symp_doc:
            logger.info(f"Retrieved symptom: {last_symp_doc['symptom']}")
            return last_symp_doc['symptom']
        else:
            logger.info("No symptoms found in database")
            return "couldn't find any relevant note"
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving symptom: {e}")
        return "Error retrieving note from database"
    except Exception as e:
        logger.error(f"Unexpected error while retrieving symptom: {e}")
        return "Error retrieving note from database"
    
def get_temperature_from_db() -> float | None:
    try:
        last_temp_doc = temperature_collection.find_one(sort=[("_id", DESCENDING)])
        if last_temp_doc:
            logger.info(f"Retrieved temp: {last_temp_doc['temperature']}")
            return float(last_temp_doc['temperature'])
        else:
            logger.info("No temp found in database")
            return None
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving temp: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while retrieving temp: {e}")
        return None


def get_all_temperatures_from_db() -> List[Dict[str, Any]]:
    """
    Retrieves all temperature records from the database.
    
    Returns:
        List[Dict[str, Any]]: List of temperature documents, sorted by timestamp descending
    """
    try:
        temperatures = list(temperature_collection.find(
            sort=[("timestamp", DESCENDING)]
        ))
        
        # Convert ObjectId to string for each document
        for temp in temperatures:
            temp['_id'] = str(temp['_id'])
        
        logger.info(f"Retrieved {len(temperatures)} temperature records")
        return temperatures
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving temperatures: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error while retrieving temperatures: {e}")
        return []


def get_user_symptoms(phone_number: str) -> List[Dict[str, Any]]:
    """
    Retrieves all symptoms for a specific user by phone number.
    
    Args:
        phone_number (str): The phone number of the user
        
    Returns:
        List[Dict[str, Any]]: List of symptom documents for the user
    """
    try:
        if not phone_number:
            logger.warning("No phone number provided to get_user_symptoms")
            return []
            
        symptoms = list(symptoms_collection.find(
            {"phone_number": phone_number},
            sort=[("timestamp", DESCENDING)]
        ))
        
        logger.info(f"Retrieved {len(symptoms)} symptoms for user: {phone_number}")
        return symptoms
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving symptoms for user {phone_number}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error while retrieving symptoms for user {phone_number}: {e}")
        return []

def append_symptom(symptom: str, phone_number: str = None) -> bool:
    """
    Appends a new symptom to a user's existing symptoms.
    This is useful for updating a patient's condition with new information.
    
    Args:
        symptom (str): The symptom to append
        phone_number (str, optional): The user's phone number
        
    Returns:
        bool: True if successful, False otherwise
    """
    return save_symptom(symptom, phone_number)  # Currently the same as save_symptom

def query_perplexity(query: str):
    url = "https://api.perplexity.ai/chat/completions"

    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "sonar",
        "messages": [
            { "role": "system", "content": "You are an AI assistant." },
            { "role": "user", "content": query },
        ],
        "max_tokens": 1024,
    }

    response = requests.post(url, headers=headers, json=data)
    citations = response.json()['citations']
    output = response.json()['choices'][0]['message']['content']
    return output

def search_patient_query(note: str) -> str:
    result = query_perplexity(note)
    return result

def check_persistent_symptom(caller_id: str, symptom_type: str) -> bool:
    try:
        # Query by phone_number instead of caller_id
        symptoms = symptoms_collection.find(
            {"phone_number": caller_id},  # Changed from caller_id to phone_number
            sort=[("timestamp", -1)]
        )
        
        symptoms_list = list(symptoms)
        logger.info(f"Found {len(symptoms_list)} symptoms for phone number {caller_id}")
        
        if len(symptoms_list) < 2:
            logger.info("No previous symptoms found")
            return False
            
        # Get the previous symptom (index 1 since we're sorted newest first)
        previous_symptom = symptoms_list[1]
        
        logger.info(f"Previous symptom was: {previous_symptom.get('symptom')}")
        
        # Check if the previous symptom was of the specified type
        return symptom_type.lower() in previous_symptom.get('symptom', '').lower()
        
    except Exception as e:
        logger.error(f"Error checking persistent symptom: {str(e)}")
        return False
    
def save_appointment(note: str) -> bool:
    result = appointments_collection.insert_one({"apt": note})
    if result.inserted_id:
        return True
    else:
        return False

def save_user_image(phone_number: str, image_url: str, cloudinary_id: str, created_at: datetime.datetime) -> bool:
    try:
        logger.info(f"Attempting to save image for user: {phone_number}")
        
        document = {
            "phone_number": phone_number,
            "image_url": image_url,
            "cloudinary_id": cloudinary_id,
            "created_at": created_at
        }
        logger.info(f"Inserting image document: {document}")
        
        result = images_collection.insert_one(document)
        if result.inserted_id:
            logger.info(f"Image saved successfully with ID: {result.inserted_id}")
            return True
        else:
            logger.warning("Failed to save image, no inserted_id returned")
            return False
    except PyMongoError as e:
        logger.error(f"MongoDB error while saving image: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while saving image: {e}")
        return False

def get_all_images_from_db() -> List[Dict[str, Any]]:
    try:
        images = list(images_collection.find(
            sort=[("created_at", DESCENDING)]
        ))
        for image in images:
            image['_id'] = str(image['_id'])
        logger.info(f"Retrieved {len(images)} images")
        print(f"Found images: {images}") 
        return images
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving images: {e}")
        return []
    
def save_pain(pain: float, phone_number: str = None) -> bool:
    try:
        logger.info(f"Attempting to save pain: {pain} for user: {phone_number}")
        if not isinstance(pain, (int, float)):
            logger.warning(f"Invalid pain format: {pain}")
            return False
            
        document = {
            "pain": pain,
            "phone_number": phone_number,
            "timestamp": datetime.datetime.now()
        }
        logger.info(f"Inserting document: {document}")
        
        result = pain_collection.insert_one(document)
        if result.inserted_id:
            logger.info(f"Pain saved successfully with ID: {result.inserted_id}")
            return True
        else:
            logger.warning("Failed to save Pain, no inserted_id returned")
            return False
    except PyMongoError as e:
        logger.error(f"MongoDB error while saving Pain: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while saving Pain: {e}")
        return False
      

def get_all_pains_from_db() -> List[Dict[str, Any]]:
    try:
        pains = list(pain_collection.find(
            sort=[("timestamp", DESCENDING)]
        ))
        for pain in pains:
            pain['_id'] = str(pain['_id'])
        logger.info(f"Retrieved {len(pains)} pain records")
        print(f"Found pains: {pains}") 
        return pains    
    except PyMongoError as e:
        logger.error(f"MongoDB error while retrieving pains: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error while retrieving pains: {e}")
        return []
    
def save_text(text: str, phone_number: str = None) -> bool:
    try:
        logger.info(f"Attempting to save text: {text} for user: {phone_number}")
        if not isinstance(text, str):
            logger.warning(f"Invalid text format: {text}")
            return False
            
        document = {
            "text": text,
            "phone_number": phone_number,
            "timestamp": datetime.datetime.now()
        }
        logger.info(f"Inserting document: {document}")
        
        result = text_collection.insert_one(document)
        if result.inserted_id:
            logger.info(f"Text saved successfully with ID: {result.inserted_id}")
            return True
        else:
            logger.warning("Failed to save Text, no inserted_id returned")
            return False
    except PyMongoError as e:
        logger.error(f"MongoDB error while saving Text: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while saving Text: {e}")
        return False
      
