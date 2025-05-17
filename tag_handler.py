import logging
import os
import tempfile
from mutagen.id3 import ID3
from mutagen.id3._frames import TIT2, TPE1, TPE2, TALB, TDRC, TCON, TCOM, COMM, TRCK, TLEN, USLT, APIC
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.asf import ASF
from mutagen.aiff import AIFF
from mutagen.monkeysaudio import MonkeysAudio
from mutagen.musepack import Musepack
from mutagen._util import MutagenError
from models import SmartRule, db
from main import app
import smart_rules

logger = logging.getLogger(__name__)

def get_valid_tag_fields():
    """Return a list of valid ID3 tag fields supported by this bot."""
    return [
        'title', 'artist', 'album', 'album_artist', 'year', 'genre', 'composer', 
        'comment', 'track', 'length', 'lyrics', 'picture'
    ]

def get_tag_field_names_arabic():
    """Return a dictionary mapping tag fields to their Arabic names."""
    return {
        'title': 'العنوان',
        'artist': 'الفنان',
        'album': 'الألبوم',
        'album_artist': 'فنان الألبوم',
        'year': 'السنة',
        'genre': 'النوع',
        'composer': 'الملحن',
        'comment': 'تعليق',
        'track': 'رقم المسار',
        'length': 'المدة',
        'lyrics': 'كلمات الأغنية',
        'picture': 'صورة الغلاف'
    }

def extract_lyrics(file_path):
    """
    Enhanced extraction of lyrics from audio files, with support for multiple formats
    and special handling for different encoding methods.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        str: Lyrics text or empty string if no lyrics found
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return ""
        
    logger.info(f"Attempting to extract lyrics from: {file_path}")
    
    try:
        file_type = get_file_type(file_path)
        logger.info(f"File type detected: {file_type}")
        
        if file_type == 'mp3':
            # MP3 files (ID3 tags)
            try:
                # First try direct ID3 approach
                audio = ID3(file_path)
                
                # Log all frame keys for debugging
                logger.info(f"ID3 frames found: {list(audio.keys())}")
                
                # Look for any USLT frame (unsynchronized lyrics)
                for key in audio.keys():
                    if key.startswith('USLT'):
                        uslt_frame = audio[key]
                        logger.info(f"Found USLT frame: {key}")
                        if hasattr(uslt_frame, 'text'):
                            logger.info("USLT frame has text attribute, returning lyrics")
                            return uslt_frame.text
                        elif hasattr(uslt_frame, 'desc') and hasattr(uslt_frame, 'encoding'):
                            # Some USLT frames use a special encoding
                            logger.info("USLT frame has desc and encoding attributes")
                            if hasattr(uslt_frame, 'text'):
                                return uslt_frame.text
                            else:
                                # Try to get raw lyrics content
                                try:
                                    return str(uslt_frame)
                                except:
                                    pass
                
                # Try to find SYLT (synchronized lyrics) frames
                for key in audio.keys():
                    if key.startswith('SYLT'):
                        logger.info(f"Found SYLT frame: {key}")
                        try:
                            # Extract text from synchronized lyrics (without timestamps)
                            sylt_frame = audio[key]
                            if hasattr(sylt_frame, 'text'):
                                return '\n'.join([line for _, line in sylt_frame.text])
                        except Exception as sylt_err:
                            logger.error(f"Error extracting SYLT frame: {sylt_err}")
                
                # If we're here, there's no USLT/SYLT frame
                # Try alternate methods - some files store lyrics in comments or other fields
                if 'COMM' in audio:
                    # Check if comment contains lyrics
                    logger.info("Trying to extract lyrics from COMM frame")
                    for comm_frame in audio.getall('COMM'):
                        comment = ""
                        if hasattr(comm_frame, 'text'):
                            comment = comm_frame.text
                        else:
                            comment = str(comm_frame)
                        
                        # If the comment is long, it might be lyrics
                        if len(comment) > 100:  
                            logger.info(f"Found long comment ({len(comment)} chars), might be lyrics")
                            return comment
                
                # Check for TXXX frames with lyrics
                for key in audio.keys():
                    if key.startswith('TXXX'):
                        logger.info(f"Checking TXXX frame: {key}")
                        txxx_frame = audio[key]
                        # Check if this is a lyrics frame by description
                        if hasattr(txxx_frame, 'desc') and 'LYRICS' in txxx_frame.desc.upper():
                            logger.info(f"Found lyrics in TXXX frame with desc: {txxx_frame.desc}")
                            return txxx_frame.text
                
                # Last resort: look for any very long text field that might contain lyrics
                for key in audio.keys():
                    if key.startswith('T') and key not in ['TRCK', 'TYER', 'TDRC']:  # Skip track number, year etc.
                        try:
                            text = str(audio[key])
                            if len(text) > 200:  # If text is very long, it might be lyrics
                                logger.info(f"Found long text in {key} frame, might be lyrics")
                                return text
                        except:
                            pass
                
                logger.info("No lyrics found in ID3 tags")
                
                # Check for Lyrics3 tags (another lyrics format)
                try:
                    with open(file_path, 'rb') as f:
                        # Try to identify Lyrics3v2 format
                        f.seek(-128-9, 2)  # Go to possible Lyrics3 tag position
                        if f.read(9) == b'LYRICS200':
                            logger.info("Found Lyrics3v2 tag, but parser not implemented")
                            # This file has Lyrics3v2 tag - would need more parsing
                            # (implementation omitted for complexity reasons)
                except Exception as lyrics3_err:
                    logger.error(f"Error checking Lyrics3 tags: {lyrics3_err}")
                
            except Exception as id3_err:
                logger.error(f"Error extracting lyrics from ID3: {id3_err}")
        
        elif file_type in ['flac', 'ogg', 'opus']:
            logger.info(f"Processing {file_type} file for lyrics")
            # FLAC/OGG files
            try:
                if file_type == 'flac':
                    audio = FLAC(file_path)
                elif file_type == 'ogg':
                    audio = OggVorbis(file_path)
                else:  # opus
                    audio = OggOpus(file_path)
                
                # Log all comment fields for debugging
                logger.info(f"Vorbis fields found: {list(audio.keys())}")
                
                # Check for lyrics tags - different vorbis comment fields that might have lyrics
                possible_lyrics_fields = [
                    'lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS', 
                    'lyric', 'LYRIC', 'LYRICS:SYNC', 'SYNCED_LYRICS',
                    'lyrics-XXX', 'UNSYNCED_LYRICS', 'SYNCHRONIZED_LYRICS',
                    'LYRICS_TEXT', 'LYRICS_SYNCHRONISED', 'LYRICS_UNSYNCED',
                    'LYRICS_SYNCHRONISED:ara', 'LYRICS_UNSYNCED:ara'
                ]
                
                for field in possible_lyrics_fields:
                    if field in audio:
                        logger.info(f"Found lyrics in field: {field}")
                        return audio[field][0]
                
                # Try to find any field that might contain lyrics
                for field in audio.keys():
                    if 'LYR' in field.upper():
                        logger.info(f"Found potential lyrics field: {field}")
                        return audio[field][0]
                        
                logger.info("No lyrics found in vorbis comments")
            except Exception as vorbis_err:
                logger.error(f"Error extracting lyrics from vorbis comments: {vorbis_err}")
        
        elif file_type == 'mp4':
            # MP4/M4A files
            try:
                logger.info("Processing MP4/M4A file for lyrics")
                audio = MP4(file_path)
                
                # Log all atoms for debugging
                logger.info(f"MP4 atoms found: {list(audio.keys())}")
                
                if '©lyr' in audio:
                    logger.info("Found lyrics in ©lyr atom")
                    return audio['©lyr'][0]
                    
                # Look for other possible lyrics fields
                possible_lyrics_atoms = ['lyrics', 'LYRICS', '©lyc', 'lrcT']
                for atom in possible_lyrics_atoms:
                    if atom in audio:
                        logger.info(f"Found lyrics in atom: {atom}")
                        return audio[atom][0]
                        
                logger.info("No lyrics found in MP4 atoms")
            except Exception as mp4_err:
                logger.error(f"Error extracting lyrics from MP4: {mp4_err}")
            
        # For other formats or if nothing found, return empty string
        logger.info(f"No lyrics found in {file_type} file")
        return ""
    
    except Exception as e:
        logger.error(f"General error extracting lyrics: {e}")
        return ""

def extract_album_art(file_path):
    """
    Extract album art from an audio file.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        tuple: (image_data, mime_type) or (None, None) if no album art found
    """
    try:
        file_type = get_file_type(file_path)
        
        if file_type == 'mp3':
            # MP3 files
            id3 = ID3(file_path)
            
            for tag in id3.values():
                if tag.FrameID == 'APIC':
                    return tag.data, tag.mime
        
        elif file_type == 'flac':
            # FLAC files
            audio = FLAC(file_path)
            
            if audio.pictures:
                picture = audio.pictures[0]
                return picture.data, picture.mime
        
        elif file_type == 'mp4':
            # MP4/M4A/AAC files
            audio = MP4(file_path)
            
            if 'covr' in audio:
                cover = audio['covr'][0]
                # Determine mime type based on format
                # MP4 cover types: 0=GIF, 1=JPEG, 2=PNG, 3=BMP
                mime_types = {
                    0: 'image/gif',
                    1: 'image/jpeg',
                    2: 'image/png',
                    3: 'image/bmp',
                    13: 'image/jpeg',  # Common value for JPEG
                    14: 'image/png'    # Common value for PNG
                }
                
                # Try to determine format, default to JPEG if unknown
                mime = 'image/jpeg'
                if hasattr(cover, 'imageformat'):
                    mime = mime_types.get(cover.imageformat, 'image/jpeg')
                
                return bytes(cover), mime
        
        elif file_type == 'ogg' or file_type == 'opus':
            # OGG files might have METADATA_BLOCK_PICTURE
            if file_type == 'ogg':
                audio = OggVorbis(file_path)
            else:
                audio = OggOpus(file_path)
            
            if 'metadata_block_picture' in audio:
                import base64
                from mutagen.flac import Picture
                
                picture_data = base64.b64decode(audio['metadata_block_picture'][0])
                picture = Picture(picture_data)
                return picture.data, picture.mime
        
        elif file_type == 'asf':
            # WMA files
            audio = ASF(file_path)
            
            if 'WM/Picture' in audio:
                picture = audio['WM/Picture'][0]
                if hasattr(picture, 'value'):
                    # Some versions of mutagen store it differently
                    return picture.value, 'image/jpeg'  # Assuming JPEG
        
        elif file_type == 'aiff':
            # AIFF files
            audio = AIFF(file_path)
            if hasattr(audio, 'tags') and audio.tags:
                for tag in audio.tags.values():
                    if tag.FrameID == 'APIC':
                        return tag.data, tag.mime
        
        # No album art found or unsupported format
        return None, None
        
    except Exception as e:
        logger.error(f"Error extracting album art: {e}")
        return None, None

def get_file_type(file_path):
    """
    Determine the audio file type based on extension.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        str: Audio file type
    """
    extension = os.path.splitext(file_path)[1].lower()
    if extension == '.mp3':
        return 'mp3'
    elif extension == '.flac':
        return 'flac'
    elif extension == '.wav':
        return 'wav'
    elif extension in ['.m4a', '.mp4', '.aac']:
        return 'mp4'
    elif extension == '.ogg':
        return 'ogg'
    elif extension == '.opus':
        return 'opus'
    elif extension in ['.wma', '.asf']:
        return 'asf'
    elif extension == '.aiff':
        return 'aiff'
    elif extension == '.ape':
        return 'ape'
    elif extension == '.mpc':
        return 'mpc'
    else:
        # Default to MP3 for unknown extensions
        return 'mp3'

def get_audio_tags(file_path):
    """
    Extract tags from an audio file.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        dict: Dictionary of tag names and values
    """
    try:
        file_type = get_file_type(file_path)
        tags = {}
        has_album_art = False
        
        # Process file based on its type
        if file_type == 'mp3':
            # MP3 files use ID3 tags
            audio = MP3(file_path)
            
            # Check if file has ID3 tags
            if not audio.tags:
                try:
                    # Try to add ID3 frame if it doesn't exist
                    audio.add_tags()
                    audio.save()
                    logger.info(f"Added ID3 tags to {file_path}")
                    return {}
                except Exception as e:
                    logger.error(f"Error adding ID3 tags: {e}")
                    return {}
            
            id3 = ID3(file_path)
            
            # Map common ID3 frames to our simplified tag names
            if 'TIT2' in id3:  # Title
                tags['title'] = str(id3['TIT2'])
            
            if 'TPE1' in id3:  # Artist
                tags['artist'] = str(id3['TPE1'])
            
            if 'TPE2' in id3:  # Album Artist
                tags['album_artist'] = str(id3['TPE2'])
            
            if 'TALB' in id3:  # Album
                tags['album'] = str(id3['TALB'])
            
            if 'TDRC' in id3:  # Year/Release date
                tags['year'] = str(id3['TDRC'])
            
            if 'TCON' in id3:  # Genre
                tags['genre'] = str(id3['TCON'])
            
            if 'TCOM' in id3:  # Composer
                tags['composer'] = str(id3['TCOM'])
            
            if 'COMM' in id3:  # Comment
                tags['comment'] = str(id3['COMM'])
            
            if 'TRCK' in id3:  # Track number
                tags['track'] = str(id3['TRCK'])
            
            if 'TLEN' in id3:  # Length
                tags['length'] = str(id3['TLEN'])
            
            # Extract lyrics using our specialized function
            lyrics = extract_lyrics(file_path)
            if lyrics:
                tags['lyrics'] = lyrics
            
            # Check for album art
            for tag in id3.values():
                if tag.FrameID == 'APIC':
                    has_album_art = True
                    break
            
        elif file_type == 'flac':
            # FLAC files
            audio = FLAC(file_path)
            
            # Map common tags
            if 'title' in audio:
                tags['title'] = audio['title'][0]
            if 'artist' in audio:
                tags['artist'] = audio['artist'][0]
            if 'album' in audio:
                tags['album'] = audio['album'][0]
            if 'date' in audio:
                tags['year'] = audio['date'][0]
            if 'genre' in audio:
                tags['genre'] = audio['genre'][0]
            if 'composer' in audio:
                tags['composer'] = audio['composer'][0]
            if 'comment' in audio:
                tags['comment'] = audio['comment'][0]
            if 'tracknumber' in audio:
                tags['track'] = audio['tracknumber'][0]
                
            # Extract lyrics using specialized function
            lyrics = extract_lyrics(file_path)
            if lyrics:
                tags['lyrics'] = lyrics
            
            # Check for album art
            if audio.pictures:
                has_album_art = True
            
        elif file_type == 'wav':
            # WAV files
            try:
                audio = WAVE(file_path)
                # Some WAV files might have ID3 tags
                if hasattr(audio, 'tags') and audio.tags:
                    for key, value in audio.tags.items():
                        tags[key.lower()] = str(value[0])
            except Exception as e:
                logger.error(f"Error reading WAV tags: {e}")
            
        elif file_type == 'mp4':
            # MP4/M4A/AAC files
            audio = MP4(file_path)
            
            # Map common tags
            if '\xa9nam' in audio:  # Title
                tags['title'] = audio['\xa9nam'][0]
            if '\xa9ART' in audio:  # Artist
                tags['artist'] = audio['\xa9ART'][0]
            if '\xa9alb' in audio:  # Album
                tags['album'] = audio['\xa9alb'][0]
            if '\xa9day' in audio:  # Year
                tags['year'] = audio['\xa9day'][0]
            if '\xa9gen' in audio:  # Genre
                tags['genre'] = audio['\xa9gen'][0]
            if '\xa9wrt' in audio:  # Composer
                tags['composer'] = audio['\xa9wrt'][0]
            if '\xa9cmt' in audio:  # Comment
                tags['comment'] = audio['\xa9cmt'][0]
            if 'trkn' in audio:  # Track number
                tags['track'] = str(audio['trkn'][0][0])
            
            # Check for album art
            if 'covr' in audio:
                has_album_art = True
            
        elif file_type == 'ogg':
            # OGG Vorbis files
            audio = OggVorbis(file_path)
            
            # Map common tags
            for key in ['title', 'artist', 'album', 'date', 'genre', 'composer', 'comment', 'tracknumber']:
                if key in audio:
                    tags[key.replace('tracknumber', 'track').replace('date', 'year')] = audio[key][0]
            
        elif file_type == 'opus':
            # Opus files
            audio = OggOpus(file_path)
            
            # Map common tags
            for key in ['title', 'artist', 'album', 'date', 'genre', 'composer', 'comment', 'tracknumber']:
                if key in audio:
                    tags[key.replace('tracknumber', 'track').replace('date', 'year')] = audio[key][0]
            
        elif file_type == 'asf':
            # WMA files
            audio = ASF(file_path)
            
            # Map common tags
            if 'Title' in audio:
                tags['title'] = str(audio['Title'][0])
            if 'Author' in audio:
                tags['artist'] = str(audio['Author'][0])
            if 'WM/AlbumTitle' in audio:
                tags['album'] = str(audio['WM/AlbumTitle'][0])
            if 'WM/Year' in audio:
                tags['year'] = str(audio['WM/Year'][0])
            if 'WM/Genre' in audio:
                tags['genre'] = str(audio['WM/Genre'][0])
            if 'WM/Composer' in audio:
                tags['composer'] = str(audio['WM/Composer'][0])
            if 'Description' in audio:
                tags['comment'] = str(audio['Description'][0])
            if 'WM/TrackNumber' in audio:
                tags['track'] = str(audio['WM/TrackNumber'][0])
            
            # Check for album art
            if 'WM/Picture' in audio:
                has_album_art = True
            
        elif file_type == 'aiff':
            # AIFF files
            audio = AIFF(file_path)
            if hasattr(audio, 'tags') and audio.tags:
                id3 = audio.tags
                
                # Map common ID3 frames to our simplified tag names
                if 'TIT2' in id3:  # Title
                    tags['title'] = str(id3['TIT2'])
                if 'TPE1' in id3:  # Artist
                    tags['artist'] = str(id3['TPE1'])
                if 'TALB' in id3:  # Album
                    tags['album'] = str(id3['TALB'])
                if 'TDRC' in id3:  # Year/Release date
                    tags['year'] = str(id3['TDRC'])
                if 'TCON' in id3:  # Genre
                    tags['genre'] = str(id3['TCON'])
                if 'TCOM' in id3:  # Composer
                    tags['composer'] = str(id3['TCOM'])
                if 'COMM' in id3:  # Comment
                    tags['comment'] = str(id3['COMM'])
                if 'TRCK' in id3:  # Track number
                    tags['track'] = str(id3['TRCK'])
                
                # Check for album art
                for tag in id3.values():
                    if tag.FrameID == 'APIC':
                        has_album_art = True
                        break
            
        elif file_type == 'ape':
            # Monkey's Audio files
            audio = MonkeysAudio(file_path)
            if hasattr(audio, 'tags') and audio.tags:
                for key, value in audio.tags.items():
                    tags[key.lower()] = value[0]
            
        elif file_type == 'mpc':
            # Musepack files
            audio = Musepack(file_path)
            if hasattr(audio, 'tags') and audio.tags:
                for key, value in audio.tags.items():
                    tags[key.lower()] = value[0]
        
        # Add has_album_art flag
        tags['has_album_art'] = has_album_art
        tags['file_type'] = file_type
        
        return tags
    
    except MutagenError as e:
        logger.error(f"Mutagen error processing {file_path}: {e}")
        raise Exception(f"خطأ في قراءة ملف الصوت: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        raise Exception(f"خطأ في معالجة ملف الصوت: {str(e)}")

def set_audio_tags(file_path, new_tags):
    """
    Set tags for an audio file.
    
    Args:
        file_path: Path to the audio file
        new_tags: Dictionary of tag names and values to set
        
    Returns:
        bool: True if successful, raises exception otherwise
    """
    try:
        file_type = get_file_type(file_path)
        logger.info(f"Processing file of type: {file_type}")
        
        # First, get all existing tags to preserve them
        existing_tags = {}
        try:
            existing_tags = get_audio_tags(file_path)
            logger.info(f"Retrieved existing tags: {existing_tags}")
        except Exception as e:
            logger.warning(f"Could not retrieve existing tags (this may be normal for new files): {e}")
        
        # Merge existing tags with new tags
        # New tags will override existing ones with the same name
        merged_tags = existing_tags.copy()  # Start with existing tags
        for key, value in new_tags.items():
            merged_tags[key] = value  # Override with new values
        
        logger.info(f"Merged tags: {merged_tags}")
        
        # Create a temporary copy of the file to work on
        # This helps avoid file locking issues and ensures the changes are saved properly
        temp_dir = os.path.dirname(file_path)
        with tempfile.NamedTemporaryFile(suffix=f'.{file_type}', dir=temp_dir, delete=False) as temp_file:
            temp_path = temp_file.name
            logger.info(f"Created temporary file: {temp_path}")
            
            # Copy the original file to the temporary file
            with open(file_path, 'rb') as src_file:
                temp_file.write(src_file.read())
        
        logger.info(f"Working with temporary file: {temp_path}")
        
        if file_type == 'mp3':
            # MP3 files - use ID3 tags
            try:
                audio = ID3(temp_path)
                logger.info("Successfully opened existing ID3 tags")
            except:
                # If there are no tags, add them
                logger.info("No existing ID3 tags, creating new ones")
                audio = MP3(temp_path)
                audio.add_tags()
                audio = ID3(temp_path)
            
            # Set the tags based on the merged values
            if 'title' in merged_tags:
                logger.info(f"Setting title to: {merged_tags['title']}")
                audio['TIT2'] = TIT2(encoding=3, text=merged_tags['title'])
                
            if 'artist' in merged_tags:
                logger.info(f"Setting artist to: {merged_tags['artist']}")
                audio['TPE1'] = TPE1(encoding=3, text=merged_tags['artist'])
                
            if 'album_artist' in merged_tags:
                logger.info(f"Setting album_artist to: {merged_tags['album_artist']}")
                audio['TPE2'] = TPE2(encoding=3, text=merged_tags['album_artist'])
                
            if 'album' in merged_tags:
                logger.info(f"Setting album to: {merged_tags['album']}")
                audio['TALB'] = TALB(encoding=3, text=merged_tags['album'])
                
            if 'year' in merged_tags:
                logger.info(f"Setting year to: {merged_tags['year']}")
                audio['TDRC'] = TDRC(encoding=3, text=merged_tags['year'])
                
            if 'genre' in merged_tags:
                logger.info(f"Setting genre to: {merged_tags['genre']}")
                audio['TCON'] = TCON(encoding=3, text=merged_tags['genre'])
                
            if 'composer' in merged_tags:
                logger.info(f"Setting composer to: {merged_tags['composer']}")
                audio['TCOM'] = TCOM(encoding=3, text=merged_tags['composer'])
                
            if 'comment' in merged_tags:
                logger.info(f"Setting comment to: {merged_tags['comment']}")
                audio['COMM'] = COMM(encoding=3, lang='eng', desc='', text=merged_tags['comment'])
                
            if 'track' in merged_tags:
                logger.info(f"Setting track to: {merged_tags['track']}")
                audio['TRCK'] = TRCK(encoding=3, text=merged_tags['track'])
                
            if 'length' in merged_tags:
                logger.info(f"Setting length to: {merged_tags['length']}")
                audio['TLEN'] = TLEN(encoding=3, text=merged_tags['length'])
                
            if 'lyrics' in merged_tags and merged_tags['lyrics']:
                logger.info(f"Setting lyrics of length: {len(merged_tags['lyrics'])}")
                
                # حذف أي إطارات كلمات موجودة مسبقًا
                for key in list(audio.keys()):
                    if key.startswith('USLT'):
                        logger.info(f"Removing existing lyrics frame: {key}")
                        del audio[key]
                
                # إضافة الكلمات بتنسيق UTF-8 لدعم النصوص العربية بشكل أفضل
                audio.add(USLT(
                    encoding=3,  # UTF-8
                    lang='eng',
                    desc='',
                    text=merged_tags['lyrics']
                ))
                
                # إضافة نسخة ثانية من الكلمات بوصف مختلف لزيادة التوافقية
                audio.add(USLT(
                    encoding=3,  # UTF-8
                    lang='ara',  # للغة العربية
                    desc='Arabic',
                    text=merged_tags['lyrics']
                ))
                
                logger.info(f"Added lyrics frames with multiple encodings for better compatibility")
            
            # Handle picture/album art
            if 'picture' in merged_tags and merged_tags['picture']:
                try:
                    # Check if the picture is a file path
                    picture_data = None
                    mime_type = 'image/jpeg'  # Default mime type - JPEG is better supported by Telegram
                    
                    # Process the picture data
                    if isinstance(merged_tags['picture'], str) and os.path.isfile(merged_tags['picture']):
                        # Read from file
                        with open(merged_tags['picture'], 'rb') as pic_file:
                            picture_data = pic_file.read()
                            logger.info(f"Read {len(picture_data)} bytes from image file")
                            
                        # Try to determine the mime type from file extension
                        ext = os.path.splitext(merged_tags['picture'])[1].lower()
                        if ext == '.png':
                            mime_type = 'image/png'
                        elif ext in ['.jpg', '.jpeg']:
                            mime_type = 'image/jpeg'
                    else:
                        # Assume it's already binary data
                        picture_data = merged_tags['picture']
                        logger.info(f"Using provided binary image data, {len(picture_data)} bytes")
                    
                    if picture_data:
                        # Optimize image size for Telegram preview - using techniques from popular tag editors
                        from io import BytesIO
                        try:
                            from PIL import Image
                            
                            # Always optimize image regardless of size
                            logger.info("Optimizing image for Telegram preview (MP3 tag standard)...")
                            
                            # Load the image
                            img = Image.open(BytesIO(picture_data))
                            
                            # Resize to standard dimensions for maximum compatibility
                            # Many audio tag editors use these sizes for best results
                            target_size = 300  # Standard size used by many tag editors
                            original_size = img.size
                            width, height = original_size
                            
                            # Calculate new dimensions - maintain aspect ratio
                            if width > height:
                                new_width = target_size
                                new_height = int(height * target_size / width)
                            else:
                                new_height = target_size
                                new_width = int(width * target_size / height)
                            
                            # Always resize to standard dimensions
                            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            logger.info(f"Resized image from {original_size} to {img.size}")
                            
                            # Always convert to JPEG for maximum compatibility
                            # Most tag editors use JPEG for album art
                            buffer = BytesIO()
                            
                            # Convert to RGB if needed
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                                
                            # Save as JPEG with specific quality for tag editors
                            img.save(buffer, format='JPEG', quality=80, optimize=True)
                            mime_type = 'image/jpeg'  # Always use JPEG for best compatibility
                            
                            buffer.seek(0)
                            picture_data = buffer.read()
                            logger.info(f"Optimized image to {len(picture_data)} bytes as JPEG format")
                            
                            # Add a second copy for compatibility with different players
                            # This is a technique used by some tag editors
                            second_buffer = BytesIO()
                            img.save(second_buffer, format='JPEG', quality=80, optimize=True) 
                            second_buffer.seek(0)
                            second_picture_data = second_buffer.read()
                            has_second_picture = True
                            logger.info("Created secondary picture data for compatibility")
                        except ImportError:
                            logger.warning("PIL not available, using original image")
                        except Exception as img_err:
                            logger.error(f"Error optimizing image: {img_err}")
                        
                        # Remove existing album art
                        for key in list(audio.keys()):
                            if key.startswith('APIC'):
                                logger.info(f"Removing existing album art: {key}")
                                del audio[key]
                        
                        # Add the new album art with specific settings for Telegram compatibility
                        # Based on techniques used by popular tag editors like Mp3tag
                        logger.info(f"Adding album art using commercial tag editor technique")
                        
                        # Use a multi-frame approach like commercial tag editors
                        # First, add as front cover - the primary image
                        audio.add(APIC(
                            encoding=3,  # UTF-8
                            mime='image/jpeg',  # Always JPEG for maximum compatibility
                            type=3,  # Cover (front) - critical for thumbnails 
                            desc='Cover',
                            data=picture_data
                        ))
                        
                        # Add a second copy of the image with different type
                        # This technique is used by commercial tag editors to improve compatibility
                        if 'second_picture_data' in locals() and locals().get('second_picture_data'):
                            logger.info("Adding secondary album art frame for improved compatibility")
                            audio.add(APIC(
                                encoding=3,  # UTF-8
                                mime='image/jpeg',
                                type=0,  # Other - provides redundancy for players
                                desc='Thumbnail',
                                data=locals().get('second_picture_data')
                            ))
                        
                        logger.info(f"Added multiple album art frames to {temp_path}")
                except Exception as e:
                    logger.error(f"Error setting album art: {e}")
                    raise Exception(f"خطأ في إضافة صورة الألبوم: {str(e)}")
            
            # Save the file with ID3v2.3 - better supported for thumbnails
            logger.info(f"Saving modified MP3 file to: {temp_path}")
            audio.save(v2_version=3)  # Explicitly specify ID3v2.3 for maximum compatibility
            logger.info(f"Successfully saved ID3 tags to {temp_path}")
            
            # Now replace the original file with our modified temporary file
            logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
            os.replace(temp_path, file_path)
            logger.info(f"Successfully replaced original file with modified file")
            
        elif file_type == 'flac':
            # FLAC files
            logger.info(f"Opening FLAC file: {temp_path}")
            audio = FLAC(temp_path)
            
            # Map our tag names to FLAC tag names
            tag_map = {
                'title': 'title',
                'artist': 'artist',
                'album': 'album',
                'year': 'date',
                'genre': 'genre',
                'composer': 'composer',
                'comment': 'comment',
                'track': 'tracknumber',
                'lyrics': 'lyrics'
            }
            
            # Set the tags
            for our_tag, flac_tag in tag_map.items():
                if our_tag in new_tags:
                    logger.info(f"Setting FLAC tag {flac_tag} to: {new_tags[our_tag]}")
                    audio[flac_tag] = [new_tags[our_tag]]
            
            # Handle album art if present
            if 'picture' in new_tags and new_tags['picture']:
                try:
                    # Get picture data
                    picture_data = None
                    mime_type = 'image/jpeg'  # Default
                    
                    if isinstance(new_tags['picture'], str) and os.path.isfile(new_tags['picture']):
                        with open(new_tags['picture'], 'rb') as pic_file:
                            picture_data = pic_file.read()
                        
                        ext = os.path.splitext(new_tags['picture'])[1].lower()
                        if ext == '.png':
                            mime_type = 'image/png'
                        elif ext in ['.jpg', '.jpeg']:
                            mime_type = 'image/jpeg'
                    else:
                        picture_data = new_tags['picture']
                    
                    # Clear existing pictures
                    if audio.pictures:
                        logger.info(f"Removing existing {len(audio.pictures)} pictures")
                        audio.clear_pictures()
                    
                    # Add new picture
                    if picture_data:
                        from mutagen.flac import Picture
                        pic = Picture()
                        pic.data = picture_data
                        pic.type = 3  # Cover front
                        pic.mime = mime_type
                        pic.width = 500  # These don't have to be accurate
                        pic.height = 500
                        pic.depth = 24
                        logger.info(f"Adding new FLAC album art, size: {len(picture_data)} bytes")
                        audio.add_picture(pic)
                except Exception as e:
                    logger.error(f"Error setting FLAC album art: {e}")
            
            # Save the file
            logger.info(f"Saving modified FLAC file to: {temp_path}")
            audio.save()
            logger.info(f"Successfully saved FLAC tags")
            
            # Replace original with modified file
            logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
            os.replace(temp_path, file_path)
            logger.info(f"Successfully replaced original FLAC file")
            
        elif file_type == 'wav':
            # WAV files - limited tag support
            try:
                logger.info(f"Opening WAV file: {temp_path}")
                audio = WAVE(temp_path)
                
                # WAV files have limited tag support in mutagen
                # We'll try to handle them more safely
                if hasattr(audio, 'tags'):
                    if audio.tags is None:
                        logger.info(f"WAV file has no tags, attempting to add tags")
                        try:
                            audio.add_tags()
                            logger.info("Successfully added tags to WAV file")
                        except Exception as add_tags_err:
                            logger.warning(f"Could not add tags to WAV file: {add_tags_err}")
                    
                    # Only proceed if tags is not None
                    if audio.tags is not None:
                        for key, value in new_tags.items():
                            if key in ['title', 'artist', 'album', 'comment']:
                                try:
                                    logger.info(f"Setting WAV tag {key} to: {value}")
                                    audio.tags[key] = value
                                except Exception as tag_err:
                                    logger.warning(f"Could not set tag {key} on WAV file: {tag_err}")
                        
                        logger.info(f"Saving modified WAV file to: {temp_path}")
                        audio.save()
                        logger.info(f"Successfully saved WAV tags")
                    else:
                        logger.warning(f"WAV file {temp_path} does not support tags")
                else:
                    logger.warning(f"WAV file {temp_path} does not have tags attribute")
                
                # Replace original with modified file even if there was an error with tags
                # (the audio data itself should still be intact)
                logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
                os.replace(temp_path, file_path)
                logger.info(f"Successfully replaced original WAV file")
            except Exception as e:
                logger.error(f"Error saving WAV tags: {e}")
                # Try to clean up temp file on error
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        logger.info(f"Cleaned up temporary file after error: {temp_path}")
                except:
                    pass
                raise Exception(f"هذا الملف لا يدعم تعديل الوسوم: {str(e)}")
            
        elif file_type == 'mp4':
            # MP4/M4A/AAC files
            logger.info(f"Opening MP4/M4A file: {temp_path}")
            audio = MP4(temp_path)
            
            # Map our tag names to MP4 tag names
            tag_map = {
                'title': '\xa9nam',
                'artist': '\xa9ART',
                'album_artist': 'aART',
                'album': '\xa9alb',
                'year': '\xa9day',
                'genre': '\xa9gen',
                'composer': '\xa9wrt',
                'comment': '\xa9cmt'
            }
            
            # Set the tags
            for our_tag, mp4_tag in tag_map.items():
                if our_tag in new_tags:
                    logger.info(f"Setting MP4 tag {mp4_tag} to: {new_tags[our_tag]}")
                    audio[mp4_tag] = [new_tags[our_tag]]
            
            # Track number needs special handling
            if 'track' in new_tags:
                try:
                    track_num = int(new_tags['track'])
                    logger.info(f"Setting MP4 track number to: {track_num}")
                    audio['trkn'] = [(track_num, 0)]  # (track_number, total_tracks)
                except ValueError:
                    # If track is not a valid integer, skip it
                    logger.warning(f"Invalid track number format: {new_tags['track']}, skipping")
            
            # Handle lyrics
            if 'lyrics' in new_tags:
                logger.info(f"Setting MP4 lyrics of length: {len(new_tags['lyrics'])}")
                audio['\xa9lyr'] = [new_tags['lyrics']]
                
            # Handle album art
            if 'picture' in new_tags and new_tags['picture']:
                try:
                    picture_data = None
                    
                    # Process the picture data
                    if isinstance(new_tags['picture'], str) and os.path.isfile(new_tags['picture']):
                        with open(new_tags['picture'], 'rb') as pic_file:
                            picture_data = pic_file.read()
                            logger.info(f"Read {len(picture_data)} bytes from image file for MP4 cover")
                            
                        # Determine format
                        ext = os.path.splitext(new_tags['picture'])[1].lower()
                        cover_format = MP4Cover.FORMAT_JPEG  # Default
                        if ext == '.png':
                            cover_format = MP4Cover.FORMAT_PNG
                            logger.info("Using PNG format for MP4 cover art")
                        else:
                            logger.info("Using JPEG format for MP4 cover art")
                    else:
                        # Binary data
                        picture_data = new_tags['picture']
                        cover_format = MP4Cover.FORMAT_JPEG  # Default
                        logger.info(f"Using provided binary data for MP4 cover, {len(picture_data)} bytes")
                    
                    if picture_data:
                        logger.info(f"Adding cover art to MP4 file, size: {len(picture_data)} bytes")
                        audio['covr'] = [MP4Cover(picture_data, imageformat=cover_format)]
                except Exception as e:
                    logger.error(f"Error setting MP4 album art: {e}")
            
            # Save the file
            logger.info(f"Saving modified MP4 file to: {temp_path}")
            audio.save()
            logger.info(f"Successfully saved MP4 tags")
            
            # Replace original with modified file
            logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
            os.replace(temp_path, file_path)
            logger.info(f"Successfully replaced original MP4 file")
            
        elif file_type == 'ogg':
            # OGG Vorbis files
            logger.info(f"Opening OGG Vorbis file: {temp_path}")
            audio = OggVorbis(temp_path)
            
            # Map our tag names to OGG tag names
            tag_map = {
                'title': 'title',
                'artist': 'artist',
                'album': 'album',
                'year': 'date',
                'genre': 'genre',
                'composer': 'composer',
                'comment': 'comment',
                'track': 'tracknumber',
                'lyrics': 'lyrics',
                'album_artist': 'albumartist'
            }
            
            # Set the tags
            for our_tag, ogg_tag in tag_map.items():
                if our_tag in new_tags:
                    logger.info(f"Setting OGG tag {ogg_tag} to: {new_tags[our_tag]}")
                    audio[ogg_tag] = [new_tags[our_tag]]
            
            # Save the file
            logger.info(f"Saving modified OGG file to: {temp_path}")
            audio.save()
            logger.info(f"Successfully saved OGG tags")
            
            # Replace original with modified file
            logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
            os.replace(temp_path, file_path)
            logger.info(f"Successfully replaced original OGG file")
            
        elif file_type == 'opus':
            # Opus files
            logger.info(f"Opening Opus file: {temp_path}")
            audio = OggOpus(temp_path)
            
            # Map our tag names to Opus tag names (same as OGG)
            tag_map = {
                'title': 'title',
                'artist': 'artist',
                'album': 'album',
                'year': 'date',
                'genre': 'genre',
                'composer': 'composer',
                'comment': 'comment',
                'track': 'tracknumber',
                'lyrics': 'lyrics',
                'album_artist': 'albumartist'
            }
            
            # Set the tags
            for our_tag, opus_tag in tag_map.items():
                if our_tag in new_tags:
                    logger.info(f"Setting Opus tag {opus_tag} to: {new_tags[our_tag]}")
                    audio[opus_tag] = [new_tags[our_tag]]
            
            # Save the file
            logger.info(f"Saving modified Opus file to: {temp_path}")
            audio.save()
            logger.info(f"Successfully saved Opus tags")
            
            # Replace original with modified file
            logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
            os.replace(temp_path, file_path)
            logger.info(f"Successfully replaced original Opus file")
            
        elif file_type == 'asf':
            # WMA files
            logger.info(f"Opening ASF/WMA file: {temp_path}")
            audio = ASF(temp_path)
            
            # Map our tag names to ASF/WMA tag names
            tag_map = {
                'title': 'Title',
                'artist': 'Author',
                'album': 'WM/AlbumTitle',
                'album_artist': 'WM/AlbumArtist',
                'year': 'WM/Year',
                'genre': 'WM/Genre',
                'composer': 'WM/Composer',
                'comment': 'Description',
                'track': 'WM/TrackNumber',
                'lyrics': 'WM/Lyrics'
            }
            
            # Set the tags
            for our_tag, asf_tag in tag_map.items():
                if our_tag in new_tags:
                    logger.info(f"Setting ASF tag {asf_tag} to: {new_tags[our_tag]}")
                    audio[asf_tag] = [new_tags[our_tag]]
            
            # Save the file
            logger.info(f"Saving modified ASF/WMA file to: {temp_path}")
            audio.save()
            logger.info(f"Successfully saved ASF/WMA tags")
            
            # Replace original with modified file
            logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
            os.replace(temp_path, file_path)
            logger.info(f"Successfully replaced original ASF/WMA file")
            
        elif file_type == 'aiff':
            # AIFF files
            try:
                logger.info(f"Opening AIFF file: {temp_path}")
                audio = AIFF(temp_path)
                
                # AIFF uses ID3 tags
                if not hasattr(audio, 'tags') or not audio.tags:
                    logger.info("AIFF file has no tags, adding tags")
                    audio.add_tags()
                
                if hasattr(audio, 'tags') and audio.tags is not None:
                    id3 = audio.tags
                    
                    # Set the tags based on the provided values
                    if 'title' in new_tags:
                        logger.info(f"Setting AIFF title to: {new_tags['title']}")
                        id3['TIT2'] = TIT2(encoding=3, text=new_tags['title'])
                        
                    if 'artist' in new_tags:
                        logger.info(f"Setting AIFF artist to: {new_tags['artist']}")
                        id3['TPE1'] = TPE1(encoding=3, text=new_tags['artist'])
                        
                    if 'album_artist' in new_tags:
                        logger.info(f"Setting AIFF album_artist to: {new_tags['album_artist']}")
                        id3['TPE2'] = TPE2(encoding=3, text=new_tags['album_artist'])
                        
                    if 'album' in new_tags:
                        logger.info(f"Setting AIFF album to: {new_tags['album']}")
                        id3['TALB'] = TALB(encoding=3, text=new_tags['album'])
                        
                    if 'year' in new_tags:
                        logger.info(f"Setting AIFF year to: {new_tags['year']}")
                        id3['TDRC'] = TDRC(encoding=3, text=new_tags['year'])
                        
                    if 'genre' in new_tags:
                        logger.info(f"Setting AIFF genre to: {new_tags['genre']}")
                        id3['TCON'] = TCON(encoding=3, text=new_tags['genre'])
                        
                    if 'composer' in new_tags:
                        logger.info(f"Setting AIFF composer to: {new_tags['composer']}")
                        id3['TCOM'] = TCOM(encoding=3, text=new_tags['composer'])
                        
                    if 'comment' in new_tags:
                        logger.info(f"Setting AIFF comment to: {new_tags['comment']}")
                        id3['COMM'] = COMM(encoding=3, lang='eng', desc='', text=new_tags['comment'])
                        
                    if 'track' in new_tags:
                        logger.info(f"Setting AIFF track to: {new_tags['track']}")
                        id3['TRCK'] = TRCK(encoding=3, text=new_tags['track'])
                        
                    if 'lyrics' in new_tags:
                        logger.info(f"Setting AIFF lyrics of length: {len(new_tags['lyrics'])}")
                        id3['USLT'] = USLT(encoding=3, lang='eng', desc='', text=new_tags['lyrics'])
                    
                    # Handle picture/album art
                    if 'picture' in new_tags and new_tags['picture']:
                        try:
                            # Check if the picture is a file path
                            picture_data = None
                            mime_type = 'image/jpeg'  # Default mime type
                            
                            # Process the picture data
                            if isinstance(new_tags['picture'], str) and os.path.isfile(new_tags['picture']):
                                # Read from file
                                with open(new_tags['picture'], 'rb') as pic_file:
                                    picture_data = pic_file.read()
                                    logger.info(f"Read {len(picture_data)} bytes from image file for AIFF cover")
                                    
                                # Try to determine the mime type from file extension
                                ext = os.path.splitext(new_tags['picture'])[1].lower()
                                if ext == '.png':
                                    mime_type = 'image/png'
                                    logger.info("Using PNG format for AIFF cover art")
                                elif ext in ['.jpg', '.jpeg']:
                                    mime_type = 'image/jpeg'
                                    logger.info("Using JPEG format for AIFF cover art")
                            else:
                                # Assume it's already binary data
                                picture_data = new_tags['picture']
                                logger.info(f"Using provided binary image data for AIFF cover, {len(picture_data)} bytes")
                            
                            if picture_data:
                                # Remove existing album art
                                for key in list(id3.keys()):
                                    if key.startswith('APIC'):
                                        logger.info(f"Removing existing AIFF album art: {key}")
                                        del id3[key]
                                
                                # Add the new album art
                                logger.info(f"Adding new AIFF album art, type: {mime_type}, size: {len(picture_data)} bytes")
                                id3['APIC'] = APIC(
                                    encoding=3,  # UTF-8
                                    mime=mime_type,
                                    type=3,  # Cover (front)
                                    desc='Cover',
                                    data=picture_data
                                )
                                logger.info(f"Added album art to AIFF file")
                        except Exception as e:
                            logger.error(f"Error setting AIFF album art: {e}")
                else:
                    logger.warning(f"Failed to add tags to AIFF file: {temp_path}")
                
                # Save the file
                logger.info(f"Saving modified AIFF file to: {temp_path}")
                audio.save()
                logger.info(f"Successfully saved AIFF tags")
                
                # Replace original with modified file
                logger.info(f"Replacing original file {file_path} with modified file {temp_path}")
                os.replace(temp_path, file_path)
                logger.info(f"Successfully replaced original AIFF file")
                
            except Exception as e:
                logger.error(f"Error saving AIFF tags: {e}")
                # Try to clean up temp file on error
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        logger.info(f"Cleaned up temporary file after error: {temp_path}")
                except:
                    pass
                raise Exception(f"خطأ في حفظ وسوم AIFF: {str(e)}")
            
        elif file_type in ['ape', 'mpc']:
            # APE and Musepack have limited tag support in mutagen
            logger.warning(f"Limited tag support for {file_type} files")
            
            # Clean up the temporary file - no tags will be modified
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary file: {e}")
                
            raise Exception(f"هذا النوع من الملفات ({file_type}) له دعم محدود لتعديل الوسوم.")
            
        else:
            # Unsupported file type
            logger.warning(f"Unsupported file type: {file_type}")
            
            # Clean up the temporary file - no tags will be modified
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary file: {e}")
                
            raise Exception(f"نوع الملف غير مدعوم: {file_type}")
        
        logger.info(f"Successfully saved tags to {file_path}")
        return True
    
    except MutagenError as e:
        logger.error(f"Mutagen error saving tags to {file_path}: {e}")
        
        # Clean up the temporary file on error if it exists
        try:
            # Check if the temp file exists more safely
            temp_files = [f for f in os.listdir(os.path.dirname(file_path)) 
                          if f.startswith(os.path.basename(file_path) + "_temp")]
            
            for temp_file in temp_files:
                temp_full_path = os.path.join(os.path.dirname(file_path), temp_file)
                if os.path.exists(temp_full_path):
                    os.remove(temp_full_path)
                    logger.info(f"Cleaned up temporary file after Mutagen error: {temp_full_path}")
        except Exception as cleanup_err:
            logger.error(f"Error cleaning up temporary file: {cleanup_err}")
        
        raise Exception(f"خطأ في حفظ الوسوم: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error saving tags to {file_path}: {e}")
        
        # Clean up the temporary file on error if it exists
        try:
            # Check if the temp file exists more safely
            temp_files = [f for f in os.listdir(os.path.dirname(file_path)) 
                          if f.startswith(os.path.basename(file_path) + "_temp")]
            
            for temp_file in temp_files:
                temp_full_path = os.path.join(os.path.dirname(file_path), temp_file)
                if os.path.exists(temp_full_path):
                    os.remove(temp_full_path)
                    logger.info(f"Cleaned up temporary file after error: {temp_full_path}")
        except Exception as cleanup_err:
            logger.error(f"Error cleaning up temporary file: {cleanup_err}")
        
        raise Exception(f"خطأ في حفظ الوسوم: {str(e)}")
