"""Functions related to generating and mixing audio"""
import os
import os.path

import boto3
import sox

AUDIO_DIR = os.environ.get("AUDIO_DIR", "./audio")
ANNOUNCEMENT_AUDIO_FILE = os.path.join(AUDIO_DIR, "announcement.ogg")
UPRATED_ANNOUNCEMENT_AUDIO_FILE = os.path.join(AUDIO_DIR, "announcement_uprated.ogg")
BACKGROUND_AUDIO_FILE = os.path.join(AUDIO_DIR, "background.ogg")
SILENCE_AUDIO_FILE = os.path.join(AUDIO_DIR, "silence.ogg")


def format_arrival(train, stations):
    """Format the arrival into a speakable string"""
    return f"Now arriving at {stations[train['station']]} station.<break time=\"0.25s\"/> The <emphasis>{train['train']}</emphasis> <break time=\"0.05s\"/> number <break time=\"0.005s\"/> <emphasis>{train['number']}</emphasis> <break time=\"0.05s\"/> bound for <break time=\"0.005s\"/> <emphasis>{stations[train['destination']]}</emphasis> station."


def format_departure(train, stations):
    """Format the departure into a speakable string"""
    return f"Now departing {stations[train['station']]} station.<break time=\"0.25s\"/> The <emphasis>{train['train']}</emphasis> <break time=\"0.05s\"/> number <break time=\"0.005s\"/> <emphasis>{train['number']}</emphasis> <break time=\"0.05s\"/> bound for <break time=\"0.005s\"/> <emphasis>{stations[train['destination']]}</emphasis> station."


def create_audio(text):
    """Convert the string to audio using AWS Polly"""
    output = boto3.client("polly").synthesize_speech(
        Text=f'<speak><break time="1s"/>{text}</speak>',
        TextType="ssml",
        OutputFormat="ogg_vorbis",
        VoiceId="Matthew",
    )
    with open(ANNOUNCEMENT_AUDIO_FILE, "wb") as file:
        file.write(output["AudioStream"].read())


def mix_audio():
    """Apply some effects to the audio"""
    # Create combiner to apply effects to the announcement and pad it with silence
    tfm = sox.Combiner()

    # This one goes to eleven
    tfm.gain(10)

    # Add an echo
    tfm.echo(gain_in=0.5, gain_out=0.9, delays=[150], decays=[0.1])

    # Upgrade its channels and sample rate to be compatible with the background audio
    tfm.channels(2)
    tfm.rate(44100)

    # Prepend silence and output the file
    tfm.build(
        [SILENCE_AUDIO_FILE, ANNOUNCEMENT_AUDIO_FILE],
        UPRATED_ANNOUNCEMENT_AUDIO_FILE,
        "concatenate",
    )


def play_audio():
    """Play audio"""
    # Mix the background audio and the effects-added announcement
    sox.Combiner().preview(
        [BACKGROUND_AUDIO_FILE, UPRATED_ANNOUNCEMENT_AUDIO_FILE], "mix"
    )
