# main.py
import argparse
import yaml
from news.youtube_analyzer.youtube_analyzer import YouTubeAnalysis
import os
from news.youtube_analyzer.youtube_api import YouTubeAPI

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    config = {
        # ... other config options ...
        'llm': {
            'choice': 'openai',
            'model_name': 'gpt-3.5-turbo'
        }
    }
    
    youtube_api = YouTubeAPI(api_key=os.getenv('YOUTUBE_API_KEY'), timezone=config['timezone'])
    
    analyzer = YouTubeAnalyzer(config, youtube_api, llm_choice=config['llm']['choice'], model_name=config['llm']['model_name'])
    
    try:
        analyzer.run()
        logger.info("Analysis completed successfully")
    except Exception as e:
        logger.error(f"An error occurred during analysis: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()