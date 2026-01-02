"""
FREE AI VIDEO AUTOMATION PIPELINE
Complete main.py file - Copy everything below
"""

import os
import json
import time
import requests
from datetime import datetime
from anthropic import Anthropic
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """All configuration in one place"""
    
    # API Keys from environment/GitHub Secrets
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    HF_TOKEN = os.getenv("HF_TOKEN")
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    
    # Model settings
    CLAUDE_MODEL = "claude-3-5-haiku-20241022"  # Cheapest, fastest
    
    # Video generation settings
    HF_MODEL = "ali-vilab/text-to-video-ms-1.7b"
    VIDEO_DURATION = 8  # seconds
    VIDEO_FPS = 8  # Lower = faster generation
    VIDEO_HEIGHT = 576  # 9:16 aspect ratio
    VIDEO_WIDTH = 1024
    
    # Content settings
    NICHE = "motivation and self-improvement"
    NUM_IDEAS = 3  # Videos to generate per run
    
    # Retry settings
    MAX_RETRIES = 10
    RETRY_WAIT = 20  # seconds


# =============================================================================
# CLAUDE AI CLIENT
# =============================================================================

class ClaudeClient:
    """Generate ideas and prompts using Claude AI"""
    
    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.CLAUDE_MODEL
    
    def generate_ideas(self, num_ideas: int = 3) -> list[dict]:
        """Generate trending video ideas"""
        
        today = datetime.now().strftime('%B %d, %Y')
        
        prompt = f"""You are a viral content strategist. Generate {num_ideas} trending YouTube Shorts ideas for {today}.

NICHE: {Config.NICHE}
FORMAT: 8-second vertical videos (YouTube Shorts)
GOAL: Maximum engagement and virality

Consider:
- Current viral trends on TikTok/YouTube/Instagram
- Seasonal relevance (current month, upcoming events)
- Psychological hooks that stop scrolling
- Emotional resonance with target audience
- Shareability factor

Return ONLY valid JSON (no markdown, no extra text):
{{
  "ideas": [
    {{
      "title": "Catchy title under 100 characters",
      "description": "Clear description of video content and message",
      "hook": "First line that grabs attention immediately",
      "target_audience": "Specific demographic",
      "virality_score": 7,
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Clean up markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            return data["ideas"]
            
        except Exception as e:
            print(f"❌ Error generating ideas: {e}")
            raise
    
    def generate_video_prompt(self, idea: dict) -> str:
        """Generate detailed text-to-video prompt"""
        
        prompt = f"""Create a detailed text-to-video generation prompt for this YouTube Short idea:

TITLE: {idea['title']}
DESCRIPTION: {idea['description']}
HOOK: {idea['hook']}
TARGET: {idea['target_audience']}

REQUIREMENTS:
- Duration: 8 seconds
- Format: Vertical (9:16 aspect ratio)
- Style: Motivational, inspiring, cinematic
- Quality: Professional look
- Mood: Powerful, energetic, engaging

IMPORTANT: Keep the prompt simple and clear. Text-to-video AI works best with:
- Clear subject/scene descriptions
- Specific camera movements
- Lighting and color mood
- One main focus (not too complex)

Return ONLY the video generation prompt (no extra text, no explanations):"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            print(f"❌ Error generating video prompt: {e}")
            raise


# =============================================================================
# HUGGING FACE VIDEO GENERATOR
# =============================================================================

class VideoGenerator:
    """Generate videos using free Hugging Face models"""
    
    def __init__(self):
        self.token = Config.HF_TOKEN
        self.model_url = f"https://api-inference.huggingface.co/models/{Config.HF_MODEL}"
    
    def generate(self, prompt: str, max_retries: int = Config.MAX_RETRIES) -> Optional[str]:
        """Generate video and return file path"""
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_frames": Config.VIDEO_DURATION * Config.VIDEO_FPS,
                "height": Config.VIDEO_HEIGHT,
                "width": Config.VIDEO_WIDTH,
            }
        }
        
        print(f"🎬 Generating video...")
        print(f"   Model: {Config.HF_MODEL}")
        print(f"   Prompt: {prompt[:80]}...")
        
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.post(
                    self.model_url,
                    headers=headers,
                    json=payload,
                    timeout=300
                )
                
                # Model is loading
                if response.status_code == 503:
                    retry_count += 1
                    wait_time = Config.RETRY_WAIT * retry_count
                    print(f"   ⏳ Model loading... retry {retry_count}/{max_retries} (waiting {wait_time}s)")
                    time.sleep(wait_time)
                    continue
                
                # Success
                if response.status_code == 200:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_path = f"video_{timestamp}.mp4"
                    
                    with open(video_path, "wb") as f:
                        f.write(response.content)
                    
                    file_size = os.path.getsize(video_path) / (1024 * 1024)
                    print(f"   ✅ Video generated: {video_path} ({file_size:.2f} MB)")
                    return video_path
                
                # Other error
                print(f"   ❌ API Error {response.status_code}: {response.text[:200]}")
                retry_count += 1
                time.sleep(Config.RETRY_WAIT)
                
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
                retry_count += 1
                time.sleep(Config.RETRY_WAIT)
        
        print(f"   ❌ Failed after {max_retries} retries")
        return None


# =============================================================================
# GOOGLE SHEETS LOGGER
# =============================================================================

class SheetsLogger:
    """Log all data to Google Sheets"""
    
    def __init__(self):
        try:
            creds = Credentials.from_service_account_file(
                'sheets_creds.json',
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(Config.SPREADSHEET_ID)
            print("✅ Connected to Google Sheets")
        except Exception as e:
            print(f"❌ Failed to connect to Google Sheets: {e}")
            raise
    
    def _get_or_create_worksheet(self, name: str, headers: list[str]):
        """Get worksheet or create if doesn't exist"""
        try:
            return self.sheet.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet(name, rows=1000, cols=len(headers))
            ws.append_row(headers)
            print(f"   📋 Created new sheet: {name}")
            return ws
    
    def log_idea(self, idea: dict):
        """Log idea to Ideas_Log sheet"""
        try:
            ws = self._get_or_create_worksheet("Ideas_Log", [
                "Timestamp", "Title", "Description", "Hook",
                "Target Audience", "Virality Score", "Keywords", "Status"
            ])
            
            ws.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                idea["title"],
                idea["description"],
                idea["hook"],
                idea["target_audience"],
                idea["virality_score"],
                ", ".join(idea["keywords"]),
                "pending"
            ])
            print(f"   📝 Logged idea: {idea['title'][:50]}...")
            
        except Exception as e:
            print(f"   ⚠️  Warning: Failed to log idea: {e}")
    
    def log_video(self, idea: dict, youtube_id: str, youtube_url: str):
        """Log published video to Videos_Log sheet"""
        try:
            ws = self._get_or_create_worksheet("Videos_Log", [
                "Timestamp", "Title", "YouTube URL", "YouTube ID",
                "Status", "Virality Score", "Keywords"
            ])
            
            ws.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                idea["title"],
                youtube_url,
                youtube_id,
                "published",
                idea["virality_score"],
                ", ".join(idea["keywords"])
            ])
            print(f"   📊 Logged video to sheet")
            
        except Exception as e:
            print(f"   ⚠️  Warning: Failed to log video: {e}")
    
    def log_error(self, idea: dict, error: str):
        """Log error to Errors_Log sheet"""
        try:
            ws = self._get_or_create_worksheet("Errors_Log", [
                "Timestamp", "Title", "Error", "Stage"
            ])
            
            ws.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                idea.get("title", "Unknown"),
                str(error)[:500],
                "video_generation"
            ])
            print(f"   ⚠️  Logged error to sheet")
            
        except Exception as e:
            print(f"   ⚠️  Warning: Failed to log error: {e}")


# =============================================================================
# YOUTUBE UPLOADER
# =============================================================================

class YouTubeUploader:
    """Upload videos to YouTube"""
    
    def __init__(self):
        try:
            creds = Credentials.from_service_account_file(
                'youtube_creds.json',
                scopes=['https://www.googleapis.com/auth/youtube.upload']
            )
            self.youtube = build('youtube', 'v3', credentials=creds)
            print("✅ Connected to YouTube API")
        except Exception as e:
            print(f"❌ Failed to connect to YouTube: {e}")
            raise
    
    def upload(self, video_path: str, idea: dict) -> tuple[str, str]:
        """Upload video and return (video_id, url)"""
        
        title = idea["title"][:100]  # YouTube limit
        
        # Build description with hashtags
        keyword_tags = " ".join([f"#{kw.replace(' ', '')}" for kw in idea["keywords"][:5]])
        
        description = f"""{idea['description']}

🔥 {idea['hook']}

{keyword_tags}

#motivation #success #mindset #shorts #viral #selfimprovement"""
        
        # Build tags list
        tags = ['motivation', 'success', 'mindset', 'shorts', 'viral', 'selfimprovement']
        tags.extend([kw.replace(' ', '') for kw in idea['keywords'][:5]])
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags[:15],  # YouTube max 15 tags
                'categoryId': '22'  # People & Blogs
            },
            'status': {
                'privacyStatus': 'public',
                'madeForKids': False,
                'selfDeclaredMadeForKids': False
            }
        }
        
        print(f"📤 Uploading to YouTube...")
        print(f"   Title: {title}")
        
        try:
            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            response = None
            last_progress = 0
            
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    if progress != last_progress and progress % 20 == 0:
                        print(f"   📊 Upload progress: {progress}%")
                        last_progress = progress
            
            video_id = response['id']
            video_url = f"https://youtube.com/watch?v={video_id}"
            
            print(f"   ✅ Published: {video_url}")
            print(f"   📺 Video ID: {video_id}")
            
            return video_id, video_url
            
        except Exception as e:
            print(f"   ❌ Upload failed: {e}")
            raise


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline():
    """Execute the complete video automation pipeline"""
    
    print("=" * 70)
    print("🎬 FREE AI VIDEO AUTOMATION PIPELINE")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    print(f"🎯 Niche: {Config.NICHE}")
    print(f"📹 Videos to generate: {Config.NUM_IDEAS}")
    print("=" * 70)
    print()
    
    # Initialize all clients
    try:
        claude = ClaudeClient()
        video_gen = VideoGenerator()
        sheets = SheetsLogger()
        youtube = YouTubeUploader()
    except Exception as e:
        print(f"❌ Failed to initialize clients: {e}")
        return
    
    # Stats tracking
    stats = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "start_time": time.time()
    }
    
    try:
        # STEP 1: Generate ideas
        print("💡 STEP 1: Generating video ideas...")
        print("-" * 70)
        ideas = claude.generate_ideas(num_ideas=Config.NUM_IDEAS)
        print(f"✅ Generated {len(ideas)} ideas")
        print()
        
        # Log all ideas
        for i, idea in enumerate(ideas, 1):
            print(f"   Idea {i}: {idea['title']}")
            sheets.log_idea(idea)
        print()
        
        # STEP 2: Process each idea
        for i, idea in enumerate(ideas, 1):
            stats["total"] += 1
            
            print("=" * 70)
            print(f"📹 PROCESSING VIDEO {i}/{len(ideas)}")
            print("=" * 70)
            print(f"Title: {idea['title']}")
            print(f"Hook: {idea['hook']}")
            print(f"Target: {idea['target_audience']}")
            print(f"Virality Score: {idea['virality_score']}/10")
            print("-" * 70)
            
            try:
                # Generate video prompt
                print("\n🎨 Generating video prompt...")
                video_prompt = claude.generate_video_prompt(idea)
                print(f"   Prompt: {video_prompt[:100]}...")
                
                # Generate video
                print()
                video_path = video_gen.generate(video_prompt)
                
                if not video_path:
                    raise Exception("Video generation returned None")
                
                # Upload to YouTube
                print()
                video_id, video_url = youtube.upload(video_path, idea)
                
                # Log success
                sheets.log_video(idea, video_id, video_url)
                
                # Cleanup
                if os.path.exists(video_path):
                    os.remove(video_path)
                    print(f"   🧹 Cleaned up: {video_path}")
                
                stats["successful"] += 1
                print()
                print(f"✅ VIDEO {i} COMPLETED SUCCESSFULLY!")
                print()
                
            except Exception as e:
                stats["failed"] += 1
                print()
                print(f"❌ VIDEO {i} FAILED: {e}")
                sheets.log_error(idea, str(e))
                print()
                continue
        
        # Final summary
        elapsed = time.time() - stats["start_time"]
        
        print("=" * 70)
        print("📊 PIPELINE SUMMARY")
        print("=" * 70)
        print(f"✅ Successful: {stats['successful']}/{stats['total']}")
        print(f"❌ Failed: {stats['failed']}/{stats['total']}")
        print(f"⏱️  Total time: {elapsed/60:.1f} minutes")
        print(f"📺 Videos published: {stats['successful']}")
        print("=" * 70)
        print()
        
        if stats["successful"] > 0:
            print("🎉 Pipeline completed! Check your YouTube channel for new videos.")
        else:
            print("⚠️  No videos were published. Check error logs in Google Sheets.")
        
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        raise


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_pipeline()
