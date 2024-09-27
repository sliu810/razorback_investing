# ai_tasks.py
import openai

def apply_task(text, client, task):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": f"Please {task} for the following text:\n\n{text}"}
            ],
            max_tokens=3000
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except openai.OpenAIError as e:
        if "maximum context length" in str(e):
            print(f"Warning: Context length exceeded for transcript. Returning an empty summary.")
            return "Context length exceeded. Summary not available."
        else:
            raise e

def apply_tasks_on_all_transcripts(df, client, task):
    if 'Summary' not in df.columns:
        df['Summary'] = pd.NA

    for index, row in df.iterrows():
        if pd.isna(row['Summary']):
            transcript = row['Transcript']
            if pd.isna(transcript) or transcript == "No transcript for video":
                summary = "No summary"
            else:
                summary = apply_task(transcript, client, task)
                if not summary or summary == "Context length exceeded. Summary not available.":
                    summary = "No summary"
            df.at[index, 'Summary'] = summary

    return df