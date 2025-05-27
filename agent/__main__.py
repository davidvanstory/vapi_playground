# patient_companion/agent/__main__.py
#
from fastapi import FastAPI, Request, Response
import requests
from typing import Literal, Any, Dict, Union
import logging
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import base64
from .utils.cloudinary import cloudinary
import os
from requests.auth import HTTPBasicAuth

from agent.helpers import (
    User, get_user_from_db, save_user, save_symptom, get_symptom_from_db, 
    search_patient_query, update_user_name, callers_collection,
    get_user_symptoms, check_persistent_symptom, save_appointment, save_temp, get_temperature_from_db,
    get_all_temperatures_from_db, save_user_image, get_all_images_from_db, save_pain, get_all_pains_from_db, save_text
)

# Add Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TwilioAccountSID')
TWILIO_AUTH_TOKEN = os.environ.get('TwilioAuthToken')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Remove "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/")
def read_root() -> dict[str, str]:
    return {}

@app.get("/test/route")
def read_root() -> dict[str, str]:
    return {
        "message": "Hello Petah"
    }

@app.get("/agent/pizza")
def read_root() -> dict[str, str]:
    return {"note": "The pizza guy's number is 234. Do you want cheese or pepperoni?"}

@app.post(path="/agent/init")
async def init(request: Request) -> Dict[str, Any]:
    try:
        request_body = await request.json()
        logger.info(f"Init request body: {request_body}")
        
        caller_id = request_body['caller_id']
        logger.info(f"Initializing user with caller_id: {caller_id}")
        
        user: User | None = get_user_from_db(phone_number=caller_id)
        first_message = (
            f"""Hey there, I'm Momsen, your health companion.
I can help you track your symptoms, and answer medical questions you may have.
To start, may I have your name?"""
        )

        if not user:
            # Use a consistent name in both database and response
            initial_name = "new_user"  # This will be updated later when they give their name
            
            new_user: User = {
                "name": initial_name,
                "phone_number": caller_id
            }
            
            # Save the new user to the database
            if save_user(user=new_user):
                logger.info(f"New user created: {caller_id} with name: {initial_name}")
                # For new users, just return basic info
                return {
                    "dynamic_variables": {
                        "name": initial_name,
                        "phone_number": caller_id
                    }, 
                    "conversation_config_override": {
                        "agent": {
                            "first_message":  first_message }}
                }
            else:
                logger.error(f"Failed to save new user: {caller_id}")
                return {"status": "error", "message": "Failed to create user"}
        else:
            symptoms = get_user_symptoms(caller_id)
            if symptoms:
                print("symptoms", symptoms)
                first_message = (
                f"""Hey {user['name']}, My name is Juni, I'm here to help you track your symptoms and infection after your knee surgery. 
                 To start, can you tell me how much pain you're in on a scale of 1 to 10, and your current body temperature?"""
                )
            else:
                first_message = f"Hey {user['name']}"

        # For existing users, just return basic info too

        return {
            "dynamic_variables": {
                "name": user['name'],
                "phone_number": user['phone_number']
            }, 
            "conversation_config_override": {
                        "agent": {
                            "first_message":  first_message }}
        }
    except Exception as e:
        logger.error(f"Error in init endpoint: {str(e)}")
        return {"status": "error", "message": f"Server error: {str(e)}"}

@app.post("/agent/update-name")
async def update_name(request: Request) -> Dict[str, Any]:
    try:
        # Log that the endpoint was called
        logger.info("update-name endpoint called")
        
        # Parse the request body
        request_body = await request.json()
        logger.info(f"Parsed request body: {request_body}")
        
        # --- First, try to get caller_id from different sources ---
        caller_id = None
        
        # 1. Try request body
        if 'caller_id' in request_body:
            caller_id = request_body['caller_id']
            logger.info(f"Found caller_id in request body: {caller_id}")
        
        # 2. Try headers
        if not caller_id:
            caller_id = request.headers.get("X-Caller-ID")
            if caller_id:
                logger.info(f"Found caller_id in headers: {caller_id}")
        
        # 3. Try query params
        if not caller_id:
            caller_id = request.query_params.get("caller_id")
            if caller_id:
                logger.info(f"Found caller_id in query params: {caller_id}")
        
        # 4. Last resort: get the most recent caller
        if not caller_id:
            logger.warning("No caller_id found in request sources")
            latest_user = callers_collection.find_one(sort=[("_id", -1)])
            if latest_user:
                caller_id = latest_user.get("phone_number")
                logger.info(f"Using most recent caller: {caller_id}")
            else:
                logger.error("No callers in database and no caller_id provided")
                return {"status": "error", "message": "Missing caller_id and no recent callers found"}
        
        # --- Next, get the name to update ---
        if 'name' not in request_body:
            logger.error("Missing name parameter in request")
            return {"status": "error", "message": "Missing name parameter"}
        
        new_name = request_body['name']
        logger.info(f"Updating name for caller {caller_id} to {new_name}")
        
        # --- Now handle the database update ---
        user = get_user_from_db(phone_number=caller_id)
        
        if user:
            # Log the current state
            logger.info(f"Found existing user with name: {user.get('name')}")
            
            # Update existing user
            result = callers_collection.update_one(
                {"phone_number": caller_id},
                {"$set": {"name": new_name}}
            )
            
            success = result.acknowledged
            if success:
                logger.info(f"Successfully updated user {caller_id} name to {new_name}")
                if result.modified_count == 0:
                    logger.info("Note: No document changes were needed (name might be the same)")
            else:
                logger.error(f"Failed to update user {caller_id}")
        else:
            # Create new user
            logger.info(f"No existing user found for {caller_id}, creating new user")
            new_user = {
                "name": new_name,
                "phone_number": caller_id
            }
            result = callers_collection.insert_one(new_user)
            success = result.acknowledged
            
            if success:
                logger.info(f"Created new user with ID: {result.inserted_id}")
            else:
                logger.error(f"Failed to create new user for {caller_id}")
        
        # --- Return appropriate response ---
        if success:
            # Return updated config with new name
            return {
                "status": "success", 
                "message": f"Name updated to {new_name}",
               
                
            }
        else:
            return {"status": "error", "message": "Failed to update name"}
    
    except Exception as e:
        import traceback
        logger.error(f"Exception in update_name endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": f"Server error: {str(e)}"}

@app.post("/agent/take-symptom")
async def take_symptom(request: Request) -> Dict[str, Any]:
    try:
        request_body = await request.json()
        logger.info(f"Full request body for take-symptom: {request_body}")  # Add detailed logging
        
        if 'symptom' not in request_body:
            logger.warning("Missing 'symptom' field in request")
            return {"status": "error", "message": "Missing 'symptom' field in request"}
        
        symptom = request_body['symptom']
        
        # Check all possible sources for caller_id
        caller_id = None
        
        # 1. Try request body under different possible keys
        for key in ['caller_id', 'phone_number', 'user_id', 'from']:
            if key in request_body and request_body[key]:
                caller_id = request_body[key]
                logger.info(f"Found caller_id in request body with key '{key}': {caller_id}")
                break
        
        # 2. Try headers
        if not caller_id:
            caller_id = request.headers.get("X-Caller-ID")
            if caller_id:
                logger.info(f"Found caller_id in headers: {caller_id}")
        
        # 3. Try query params
        if not caller_id:
            caller_id = request.query_params.get("caller_id")
            if caller_id:
                logger.info(f"Found caller_id in query params: {caller_id}")
        
        # 4. Last resort: get the most recent caller
        if not caller_id:
            logger.warning("No caller_id found in request sources, attempting to find most recent caller")
            latest_user = callers_collection.find_one(sort=[("_id", -1)])
            if latest_user:
                caller_id = latest_user.get("phone_number")
                
        
        logger.info(f"Final caller_id to be used: {caller_id}")
        
        if not symptom or not isinstance(symptom, str):
            logger.warning(f"Invalid symptom format: {symptom}")
            return {"status": "error", "message": f"Invalid symptom format: {symptom}"}
        
        logger.info(f"Attempting to save symptom: {symptom} for user: {caller_id}")
        if save_symptom(symptom, caller_id):
            logger.info("Symptom saved successfully")
            # Only check for persistent cough if the current symptom is a cough
            if "cough" in symptom.lower():
                is_persistent = check_persistent_symptom(caller_id, "cough")
                logger.info(f"Checking for persistent cough. Result: {is_persistent}")
                if is_persistent:
                    return {
                        "status": "success",
                        "message": "Symptom saved successfully",
                        "conversation_config_override": {
                            "agent": {
                                "prompt": [{"prompt": "The patient has a bad cough. Recommend seeing a doctor."}],
                                "first_message": "Since your cough has been lingering, what do you think about setting up a doctors appointment. Shall we go ahead and set that up?"
                            }
                        }
                    }
            return {
                "status": "success", 
                "message": f"Symptom saved successfully: {symptom}"
            }
        else:
            logger.error("Failed to save symptom to database")
            return {"status": "error", "message": "Failed to save symptom to database"}
    except Exception as e:
        logger.error(f"Error in take_symptom endpoint: {str(e)}")
        return {"status": "error", "message": f"Server error: {str(e)}"}


@app.get("/agent/get-symptom")
async def get_symptom(request: Request) -> dict[str, str]:
    note = get_symptom_from_db()
    if note and "error" not in note.lower():
        return {
            "status": "success",
            "symptom": note
        }
    else:
        return {
            "status": "error",
            "message": note or "No symptom data available"
        }

# added for temp taking
@app.post("/agent/take-temperature")
async def take_temperature(request: Request) -> Dict[str, Any]:
    try:
        request_body = await request.json()
        temperature = float(request_body['temperature'])
        phone_number = request_body.get('phone_number')  # Optional, if you want to associate with user

        logger.info(f"Temperature received: {temperature} for user: {phone_number}")
        if save_temp(temperature, phone_number):
            return {
                "status": "success",
                "message": f"Temperature saved successfully: {temperature}°F"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to save temperature to database"
            }
    except Exception as e:
        logger.error(f"Error saving temperature: {str(e)}")
        return {"status": "error", "message": f"Server error: {str(e)}"}

@app.get("/agent/get-temperature")
async def get_temperature(request: Request) -> Dict[str, Any]:
    temperature = get_temperature_from_db()
    if temperature is None:
        return {
            "status": "error",
            "message": "No temperature data available"
        }
    return {
        "status": "success",
        "temperature": temperature
    }

@app.get("/agent/get-all-temperatures")
async def get_all_temperatures() -> Dict[str, Any]:
    try:
        temperatures = get_all_temperatures_from_db()
        print(f"Found temperatures: {temperatures}") 

        if not temperatures:
            print("No temperature records found")
            return {
                "status": "success",
                "message": "No temperature records found",
                "temperatures": []
            }
            
        return {
            "status": "success",
            "message": f"Retrieved {len(temperatures)} temperature records",
            "temperatures": temperatures
        }
    except Exception as e:
        logger.error(f"Error in get_all_temperatures endpoint: {str(e)}")
        return {
            "status": "error",
            "message": f"Server error: {str(e)}",
            "temperatures": []
        }

@app.post("/agent/search")
async def search(request: Request) -> dict[str, str]:
    request_body = await request.json()
    result = search_patient_query(request_body['search_query'])
    return {
        "result": result
    }

@app.post("/agent/schedule-appointment")
async def schedule_appointment(request: Request) -> Dict[str, Any]:
    try:
        request_body = await request.json()
        logger.info(f"Schedule appointment request body: {request_body}")
        
        if 'appointment' not in request_body:
            logger.error("Missing 'appointment' field in request")
            return {"status": "error", "message": "Missing appointment details"}
            
        if save_appointment(request_body['appointment']):
            logger.info("Appointment saved successfully")
            return {
                "status": "success",
                "message": "Appointment scheduled successfully"
            }
        else:
            logger.error("Failed to save appointment")
            return {
                "status": "error",
                "message": "Failed to save appointment to database"
            }
            
    except Exception as e:
        logger.error(f"Error in schedule_appointment endpoint: {str(e)}")
        return {"status": "error", "message": f"Server error: {str(e)}"}

@app.post("/agent/save-image")
async def save_image(request: Request) -> Dict[str, Any]:
    try:
        request_body = await request.json()
        logger.info(f"Save image request body: {request_body}")
        
        # Convert the created_at string to datetime object
        created_at = datetime.fromisoformat(request_body['created_at'].replace('Z', '+00:00'))
        
        if save_user_image(
            phone_number=request_body['phone_number'],
            image_url=request_body['image_url'],
            cloudinary_id=request_body['cloudinary_id'],
            created_at=created_at
        ):
            logger.info("Image saved successfully")
            return {
                "status": "success",
                "message": "Image saved successfully"
            }
        else:
            logger.error("Failed to save image")
            return {
                "status": "error",
                "message": "Failed to save image to database"
            }
            
    except Exception as e:
        logger.error(f"Error in save_image endpoint: {str(e)}")
        return {"status": "error", "message": f"Server error: {str(e)}"}


@app.get("/agent/get-all-images")
async def get_all_images() -> Dict[str, Any]:
    try:
        images = get_all_images_from_db()
        print(f"Found images: {images}") 

        if not images:
            return {
                "status": "success",
                "message": "No images found",
                "images": []
            }
            
        return {
            "status": "success",
            "message": f"Retrieved {len(images)} images",
            "images": images
        }
    except Exception as e:
        logger.error(f"Error in get_all_images endpoint: {str(e)}")
        return {
            "status": "error",
            "message": f"Server error: {str(e)}",
            "images": []
        }


@app.post("/agent/take-pain")
async def take_pain(request: Request) -> Dict[str, Any]:
    try:
        request_body = await request.json()
        pain = float(request_body['pain'])
        phone_number = request_body.get('phone_number')  # Optional, if you want to associate with user

        logger.info(f"Pain received: {pain} for user: {phone_number}")
        if save_pain(pain, phone_number):
            return {
                "status": "success",
                "message": f"Pain saved successfully: {pain}°F"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to save pain to database"
            }
    except Exception as e:
        logger.error(f"Error saving pain: {str(e)}")
        return {"status": "error", "message": f"Server error: {str(e)}"}
    

@app.get("/agent/get-all-pains")
async def get_all_pains() -> Dict[str, Any]:

    try:
        pains = get_all_pains_from_db()
        print(f"Found pains: {pains}") 

        if not pains:
            print("No pain records found")
            return {
                "status": "success",
                "message": "No pain records found",
                "pains": []
            }
            
        return {
            "status": "success",
            "message": f"Retrieved {len(pains)} pain records",
            "pains": pains
        }
    except Exception as e:
        logger.error(f"Error in get_all_pains endpoint: {str(e)}")
        return {
            "status": "error",
            "message": f"Server error: {str(e)}",
            "pains": []
        }


@app.post("/agent/incoming-text")
async def incoming_text(request: Request) -> Dict[str, Any]:
    try:
        # Try to parse as JSON first
        try:
            request_body = await request.json()
        except json.JSONDecodeError:
            # If JSON parsing fails, try form data
            form_data = await request.form()
            request_body = dict(form_data)
        
        print("got request body:", request_body)
        return {"message": "David's text received"}
    except Exception as e:
        logger.error(f"Error in incoming_text: {str(e)}")
        # Return a valid response even on error
        return {"message": "Error processing text", "error": str(e)}

@app.post("/agent/twilio-webhook")
async def twilio_webhook(request: Request) -> Response:
    """
    Handle incoming Twilio webhook requests for MMS (multimedia messaging)
    """
    try:
        # Parse the form data from Twilio
        form_data = await request.form()
        from_number = form_data.get('From')
        num_media = int(form_data.get('NumMedia', '0'))
        
        logger.info(f"Received Twilio webhook with {num_media} media items from {from_number}")
        
        if num_media <= 0:
            logger.info("No media found in the message")
            return Response(
                content='<Response><Message>No image was found in your message.</Message></Response>',
                media_type='text/xml',
                status_code=200
            )

        # Process each media item
        upload_results = []
        
        for i in range(num_media):
            media_url = form_data.get(f'MediaUrl{i}')
            content_type = form_data.get(f'MediaContentType{i}')
            
            if not media_url:
                logger.warning(f"Missing media URL for item {i}")
                continue
            
            # Download the media file with Twilio authentication
            logger.info(f"Downloading media from {media_url}")
            response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            if not response.ok:
                logger.error(f"Failed to download media: {response.status_code}")
                continue
            
            # Convert to base64 for Cloudinary
            base64_image = base64.b64encode(response.content).decode('utf-8')
            data_uri = f"data:{content_type};base64,{base64_image}"
            
            # Upload to Cloudinary
            try:
                logger.info("Uploading to Cloudinary")
                cloudinary_response = cloudinary.uploader.upload(
                    data_uri, 
                    folder='patient-images',
                    context={'phone_number': from_number}
                )
                
                logger.info(f"✅ MMS image uploaded to Cloudinary: {cloudinary_response.get('secure_url')}")
                
                # Save to database using your existing save_user_image function
                if save_user_image(
                    phone_number=from_number,
                    image_url=cloudinary_response.get('secure_url'),
                    cloudinary_id=cloudinary_response.get('public_id'),
                    created_at=datetime.now()
                ):
                    upload_results.append(cloudinary_response.get('secure_url'))
                    logger.info("Image saved to database successfully")
                else:
                    logger.error("Failed to save MMS image to database")
            
            except Exception as e:
                logger.error(f"Cloudinary upload error: {str(e)}")
        
        # Return success response to Twilio
        if upload_results:
            logger.info(f"Successfully processed {len(upload_results)} images")
            return Response(
                content='<Response><Message>Your image was uploaded successfully!</Message></Response>',
                media_type='text/xml',
                status_code=200
            )
        else:
            logger.warning("No images were successfully processed")
            return Response(
                content='<Response><Message>We received your message, but could not process the images. Please try again.</Message></Response>',
                media_type='text/xml',
                status_code=200
            )
            
    except Exception as e:
        logger.error(f"Error processing Twilio MMS: {str(e)}")
        return Response(
            content='<Response><Message>Sorry, we couldn\'t process your image. Please try again later.</Message></Response>',
            media_type='text/xml',
            status_code=200
        )


