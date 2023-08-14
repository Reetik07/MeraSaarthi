from flask import Flask, request, url_for ,render_template , redirect
from twilio.twiml.voice_response import Gather, VoiceResponse
from twilio.rest import Client
import openai
import urllib.request
import random
import os
from langdetect import detect

app = Flask(__name__)

class SaarthiApp:
    def __init__(self):
        self.account_sid = os.getenv('ACCOUNT_SID') #SID generated by the twilio
        self.auth_token = os.getenv('AUTH_TOKEN')  #AUTH token generated by twilio
        self.openai_api_key = os.getenv('OPENAI_API') # OPEN_AI API key 
        """
          Note: You can directly paste your keys and tokens in the string format but 
                make sure to remove os.getenv
        """
        self.client = Client(self.account_sid, self.auth_token)
        self.messages = []

    def make_call(self, number):
        """
        Initiates a phone call using the Twilio Client API.

        Args:
            number (str): The phone number to call.

        Returns:
            None
        """
        record_url = url_for("record", _external=True)
        if 'https' not in record_url:
          record_url = record_url.replace('http', 'https')
        call = self.client.calls.create(
            to="+91" + number,
            from_="+12186702677",
            url=record_url
        )
        print(call.sid)

    def transcribe(self, recording_url):
        """
        Transcribes the audio recording using OpenAI Whisper API.

        Args:
            recording_url (str): The URL of the audio recording.

        Returns:
            dict: The transcription result in dictionary format.
                  Returns None if transcription fails.
        """
        hash = str(random.getrandbits(32))
        try:
            urllib.request.urlretrieve(recording_url, hash + ".wav")
        except:
            return None
        openai.api_key = self.openai_api_key

        """
            Random names for every recording because if there 
            are multiple requests at the same time
            there is a high chance that the write request would be raised 
            at the same time which would 
            result in read/write error or it will give us the response of a different caller
        """
        audio_file = open(hash + ".wav", "rb")
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

        """
        Deleting the files as soon as we get the recording because we don't want our system to store the 
        personal recordings 

        """
        os.remove(hash + ".wav")
        return transcript

saarthi_app = SaarthiApp()

@app.route('/')
def index():
    """
    Default route that returns a greeting message.

    Returns:
        str: A greeting message.
    """
    return render_template('index.html')

@app.route("/call", methods=['GET', 'POST'])
def call():
    """
    Endpoint to initiate a phone call.

    Returns:
        str: A response message indicating the call has been initiated.
    """
    if request.method == 'POST':
        try:
            number = request.form.get("number")
            saarthi_app.make_call(number)
            return redirect(url_for('call', message='Call initiated successfully!'))
        except Exception as e:
            return redirect(url_for('call', message='Sorry! We are unable to initialize the call. Try Verifying the number on Twilio.'))
    
    message = request.args.get('message')
    return render_template('call.html', message=message)



@app.route("/record", methods=['GET', 'POST'])
def record():
    """
    Endpoint for recording a voice message.

    Returns:
        str: The TwiML response to prompt the user to leave a message.
    """
    response = VoiceResponse()
    response.say('Please leave a message after the beep.')
    response.record(action='/handle-recording', finish_on_key='*')
    return str(response)

@app.route("/handle-recording", methods=['POST'])
def handle_recording():
    """
    Endpoint to handle the recorded voice message.

    Returns:
        str: The TwiML response based on the transcription and AI-generated response.
    """
    recording_url = request.form["RecordingUrl"]
    transcription = saarthi_app.transcribe(recording_url)
    if not transcription:
        response = VoiceResponse()
        response.redirect(url_for("record"), method='POST')
        return str(response)

    transcription_text = transcription["text"] + " Create a very short answer that uses a minimum of 25 completion_tokens and a maximum of 100 completion_tokens"
    saarthi_app.messages.append({"role": "user", "content": transcription_text})

    result = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=saarthi_app.messages)
    result_text = result['choices'][0]['message']['content']

    saarthi_app.messages.append({
        "role": "assistant",
        "content": result_text
    })

    response = VoiceResponse()
    gather = Gather(action='/record', method='GET')
    if detect(result_text) == 'hi':
      gather.say(result_text, language='hi-IN')
    else:
      gather.say(result_text)
    response.append(gather)
    response.redirect(url_for("record"), method='POST')
    return str(response)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)
