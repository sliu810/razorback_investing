# main.py
import argparse
import yaml
from youtube_analysis import YouTubeAnalysis

def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def main():
    parser = argparse.ArgumentParser(description="Analyze YouTube videos")
    parser.add_argument("--channel", help="The name of the YouTube channel to analyze")
    parser.add_argument("--config", default="config.yaml", help="Path to the configuration file")
    args = parser.parse_args()

    config = load_config(args.config)
    yt_analysis = YouTubeAnalysis(config)
    yt_analysis.run(args.channel)

if __name__ == "__main__":
    main()