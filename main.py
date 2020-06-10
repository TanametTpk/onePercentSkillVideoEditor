import librosa
import numpy as np
import pretty_midi
from moviepy.editor import *
import glob
import os
import argparse

# change this for default
file_name = ''
SRC_PATH = ''
OUTPUT_PATH = ''
TMP_PATH = '__TMP_READER__'

TMP_VIDEO = TMP_PATH + "video_only.mp4"
TMP_AUDIO = TMP_PATH + "only_sound.mp3"

def allNotes(notes):
    pitchs = {}
    for note in notes:
        pitchs[note.pitch] = True
    result = list(pitchs.keys())
    result.sort()
    return result

def get_clip(note_number):
    path_clip = os.path.join(SRC_PATH, str(note_number) + ".mp4")
    clip = VideoFileClip(path_clip)
    return clip

def path_to_number(path, only_key = False):
    files = glob.glob(os.path.join(SRC_PATH, "*"))
    clips = {}
    for f in files:
        number = os.path.basename(f).split(".")[0]
        if only_key:
            clips[number] = f
        else:
            clips[number] = get_clip(number)
    return clips

def diffNote(note_in_song, note_in_src):
    return [x for x in note_in_song if x not in note_in_src]

def findNearest(array, number):
    return min(array, key=lambda x:abs(x-number))

def synthesis_sound(base, target):
    # config
    tmp_path = './tmp_{}.wav'
    target_path = os.path.join(SRC_PATH, "{}.mp4")
    
    # read video and get audio
    video = VideoFileClip(target_path.format(base))
    audio = video.audio
    
    # write sound tmp
    audio.write_audiofile(tmp_path.format(base))
    
    # read wave file
    y, sr = librosa.load(tmp_path.format(base), sr=16000)
    
    # shift sound
    steps = target - base
    y_shifted = librosa.effects.pitch_shift(y, sr, n_steps=steps)
    
    # write new wave file
    librosa.output.write_wav(tmp_path.format(target), y_shifted, sr)
    
    # read audio
    audio = AudioFileClip(tmp_path.format(target))
    video.audio = audio
    
    # write new video
    video.write_videofile(target_path.format(target))
    
    remove_list = [tmp_path.format(base), tmp_path.format(target)]
    for filePath in remove_list:
        if os.path.exists(filePath):
            os.remove(filePath)

def synthesis_not_found_sound(needed, src):
    diff = diffNote(needed, src)
    
    for d in diff:
        nearest_src = findNearest(src, d)
        synthesis_sound(nearest_src, d)

def find_min_start(notes):
    min_notes = []
    pop_index = []
    if len(notes) > 0:
        min_note = notes[0]
        min_start = min_note.start
        for i in range(len(notes)):
            note = notes[i]
            if note.start == min_start:
                min_notes.append(note)
                pop_index.append(i)
            else:
                break
        for i in range(len(pop_index)):
            index = pop_index[len(pop_index) - i - 1]
            notes.pop(index)
    return min_notes

def find_first_end(notes):
    if len(notes) > 0:
        min_end = notes[0].end
        for note in notes:
            if note.end < min_end:
                min_end = note.end
        return min_end
    return -1

def find_before(end, notes):
    if len(notes) > 0:
        min_note = notes[0]
        min_start = min_note.start
        if min_start > end:
            return []
        else:
            return find_min_start(notes)
    return []

def check_next_playing_note(playing_notes, new_start_note, current_time):
    note_still_alive = []
    for note in playing_notes[-1]:
        if note.end > current_time:
            note_still_alive.append(note)
    for note in new_start_note:
        note_still_alive.append(note)
    return note_still_alive

def split_note_frame(notes):
    playing_notes = []
    start_time = []
    end_time = []
    notes_start_before_end = []
    current_notes = []
    current_time = 0
    
    while len(notes) > 0 or len(current_notes) > 0:
        
        if len(current_notes) < 1:
            # get current notes
            current_notes = find_min_start(notes)
            
        # add current notes to playing notes list
        playing_notes.append(current_notes)

        # set start time
        start_time.append(current_notes[0].start)

        # get first end in current playing
        end = find_first_end(current_notes)

        # find notes that start before playing notes has end
        notes_start_before_end = find_before(end, notes)


        # if have note start before end then cut as end_time
        if len(notes_start_before_end) > 0:
            end_time.append(notes_start_before_end[0].start)
            
        # if not have note start then it's end by time out
        else:
            end_time.append(end)

        # get current time to check time out
        current_time = end_time[-1]

        # get playing note, remove time out note and merge new note
        current_notes = check_next_playing_note(playing_notes, notes_start_before_end, current_time)

    return playing_notes, start_time, end_time

def render_sound(notes, clips):
    sound_clips = []
    for i in range(len(notes)):
        note = notes[i]
        start_time = note.start
        end_time = note.end
        
        clip = clips[str(note.pitch)].subclip(0.5)
        # diff_time= end_time - start_time
        clip = clip.set_start(start_time)
        
        sound_clips.append(clip.audio)

    audio = CompositeAudioClip(sound_clips)
    if len(sound_clips) > 0:
        audio.write_audiofile(TMP_AUDIO, fps=sound_clips[0].fps)

def render_video(notes, clips):
    results, start , end = split_note_frame(notes)
    video_clips = []

    for i in range(len(results)):
        notes = results[i]
        start_time = start[i]
        end_time = end[i]
        for note in notes:
            clip = clips[str(note.pitch)].subclip(0.5)
            diff_time= end_time - start_time
            clip = clip.set_start(start_time)

            if diff_time <= clip.duration:
                clip = clip.set_end(end_time)
            
            video_clips.append(clip)
            
            # uncomment this if you want to process with all clips
            break

    video = CompositeVideoClip(video_clips)
    video.write_videofile(TMP_VIDEO, audio = False)

def merge_video():
    video_only = VideoFileClip(TMP_VIDEO)
    audio_only = AudioFileClip(TMP_AUDIO)
    video_only = video_only.set_audio(audio_only)
    video_only.write_videofile(OUTPUT_PATH)

def main():
    midi_data = pretty_midi.PrettyMIDI(file_name)

    notes = []
    for ins in midi_data.instruments:
        notes += ins.notes

    notes.sort(key=lambda x: x.start)
    note = allNotes(notes)

    clips = path_to_number(SRC_PATH, only_key=True)
    noteClip = list(clips.keys())
    noteClip = [ int(i) for i in noteClip ]
    noteClip.sort()

    print("synthesis sound ...")
    synthesis_not_found_sound(note, noteClip)

    print("load all video to memory ...")
    clips = path_to_number(SRC_PATH)

    print("start rendering ...")
    render_sound(notes, clips)
    render_video(notes, clips)
    merge_video()

parser = argparse.ArgumentParser(description='Generate Music Video using Midi file format as a template.')
parser.add_argument('--src_folder', type=str,  help='the folder src file with {note number}.mp4')
parser.add_argument('--output_file', type=str, default="", help="the output file. (optional. if not included, it'll just modify the input file name)")
parser.add_argument('--template_file', type=str, help="Midi file as a template")

args = parser.parse_args()

file_name = args.template_file
SRC_PATH = args.src_folder
OUTPUT_PATH = args.output_file

assert SRC_PATH != None , "why u put no src folder, checkmate!"
assert file_name != None , "why u put no midi file, dummy!"
assert OUTPUT_PATH != None , "why u put no output filename , dum!"

main()