import fetch_videos
import get_captions

def main():
    channel_id = "UCrp_UI8XtuYfpiqluWLD7Lw"
    videos_df = fetch_videos.fetch_videos(channel_id, 'hours', 2)

    for index, row in videos_df.iterrows():
        video_id = row['Video ID']
        captions = get_captions.get_captions(video_id)
        if captions:
            print(f"Captions for video {video_id}: {captions}")
        else:
            print(f"No captions found for video {video_id}")

if __name__ == "__main__":
    main()