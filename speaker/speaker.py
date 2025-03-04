#!/usr/bin/env python3

# document usage of this script
# python3 speaker.py --input /path/to/audio/file --volume 0.5

import argparse
import os
import sys
import time
import vlc
import pygame

def play_wav(file_path):
    os.environ["SDL_AUDIODRIVER"] = "alsa"
    pygame.mixer.quit()
    pygame.mixer.init()
    sound = pygame.mixer.Sound(file_path)
    playing = sound.play()
    while playing.get_busy():
        pygame.time.delay(100)

def play_mp3(file_path, volume):
    os.environ["SDL_AUDIODRIVER"] = "alsa"
    pygame.mixer.quit()
    pygame.mixer.init()
    pygame.mixer.music.set_volume(volume)
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

def main():
    if os.getuid() == 0:
        print("Warning: Running as root can cause audio device issues. Please run as a normal user.")
    
    parser = argparse.ArgumentParser(description='Play an audio file with a specified volume.')
    parser.add_argument('--input', required=True, help='Path to the audio file')
    parser.add_argument('--volume', type=float, required=True, help='Volume level (0.0 to 1.0)')
    args = parser.parse_args()
    
    if not os.path.isfile(args.input):
        print(f"Error: File '{args.input}' does not exist.")
        sys.exit(1)
    
    # if not (0.0 <= args.volume <= 1.0):
    #     # print("Error: Volume must be between 0.0 and 1.0")
    #     # sys.exit(1)
    
    file_extension = os.path.splitext(args.input)[1].lower()
    if file_extension == ".wav":
        play_wav(args.input)
    elif file_extension == ".mp3":
        play_mp3(args.input, args.volume)
    else:
        print("Error: Unsupported file format. Only .wav and .mp3 are supported.")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
