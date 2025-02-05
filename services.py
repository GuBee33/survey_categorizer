import os
import json
from tqdm import tqdm
from openai import OpenAI
import pandas as pd
import matplotlib.pyplot as plt
import re

os.environ['OPENAI_API_KEY'] = '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'

class DataLoader:
    def __init__(self, file_path,limit):
        self.file_path = file_path
        self.limit=limit

    def load_data(self):
        with open(self.file_path, 'r') as file:
            lines = file.readlines()
        question = lines[0].strip()
        answers = [line.strip() for line in lines[1:self.limit+1]]
        return question, answers

class Categorizer:
    def __init__(self, categories, api_client,model="gpt-4o"):
        self.categories_dict = {category: [] for category in categories}
        self.api_client = api_client
        self.model = model

    def categorize_answers(self, answers):
        formatted_answers = "\n".join([f"{i+1}. {answer}" for i, answer in enumerate(answers)])
        system_prompt = (
            "You will receive multiple employee survey answers and a list of existing categories. "
            "For each answer, assign up to 3 relevant category labels from the existing categories. "
            "Provide the results as a JSON array where each element is an array of categories corresponding to each answer. "
            "the response must contain only the JSON array no other string or leading/ending character"
            "Use only the Hungarian language for the category labels."
        )
        user_prompt = (
            f"Existing categories: [{', '.join(self.categories_dict.keys())}].\n\n"
            f"Survey Answers:\n{formatted_answers}\n\n"
            "Please provide the category assignments as specified."
        )
        response = self.api_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500,
            temperature=0.2,
            n=1,
            stop=None
        )
        response_text = response.choices[0].message.content.strip().replace("```json","").replace("```","")
        categories_list = json.loads(response_text)
        for i in range(len(answers)):
            categories = categories_list[i]
            for category in categories:
                if category in self.categories_dict:
                    self.categories_dict[category].append(answers[i])
                else:
                    self.categories_dict[category] = [answers[i]]
        return self.categories_dict

    def find_keys_by_value(self, target_value):
        matching_keys = []
        for key, values_list in self.categories_dict.items():
            if target_value in values_list:
                matching_keys.append(key)
        return matching_keys

class Chunker:
    def __init__(self,chunk_size):
        self.chunk_size=chunk_size
    def chunk_list(self,data):
        for i in range(0, len(data), self.chunk_size):
            yield data[i:i + self.chunk_size]

class Exporter:
    def __init__(self, categorizor, answers):
        self.categorizer = categorizor
        self.answers = answers
    
    def sanitize_filename(self,name):
        """
        Sanitize a string to be a valid filename by removing or replacing invalid characters.
        """
        # Define a pattern for invalid filename characters
        invalid_chars = r'[\s<>:"/\\|?*]'
        # Replace invalid characters with underscores
        sanitized = re.sub(invalid_chars, '_', name)
        # Optionally, remove leading/trailing whitespace and dots
        sanitized = sanitized.strip().strip('.')
        return sanitized
    def make_valid_xlsx_filename(self,name):
        """
        Convert a random string to a valid .xlsx filename.
        """
        sanitized = self.sanitize_filename(name)
        # Ensure the filename ends with .xlsx
        if not sanitized.lower().endswith('.xlsx'):
            sanitized += '.xlsx'
        return sanitized

    def dump_to_excel(self, df_sorted, sheet_name='Answers and Categories' ,excel_file='result_data.xlsx'):
        excel_file=self.make_valid_xlsx_filename(excel_file)
        sheet_name=self.sanitize_filename(sheet_name)
        data = []
        for answer in self.answers:
            categories = self.categorizer.find_keys_by_value(answer)
            data.append([answer] + categories)
        max_categories = max(len(item) - 1 for item in data)
        column_names = ['Answer'] + [f'Category{i+1}' for i in range(max_categories)]
        df = pd.DataFrame(data, columns=column_names)
        with pd.ExcelWriter(excel_file) as writer:
            df.to_excel(writer, sheet_name=sheet_name[:15], index=False)
            df_sorted.to_excel(writer, sheet_name='Summary', index=False)
        print(f"Data has been written to '{excel_file}'.")

    def plot_result(self, df_sorted):
        plt.figure(figsize=(10, 6))
        bars = plt.bar(df_sorted['Category'], df_sorted['Length'], color='skyblue')
        plt.xlabel('Category')
        plt.ylabel('Length of Arrays')
        plt.title('Histogram of Array Lengths in Descending Order')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, yval, int(yval), ha='center', va='bottom')
        plt.show()

class SurveyAnalyzer:
    def __init__(self, file_path, categories,model="gpt-4o",result_excel='result_data.xlsx',answer_limit=None,chunk_size=10):
        self.loader = DataLoader(file_path,answer_limit)
        self.client = OpenAI()
        self.categorizer = Categorizer(categories, self.client,model)
        self.chunker = Chunker(chunk_size)
        self.excel_file = result_excel
        self.chunk_size=chunk_size

    def find_keys_by_value(self, target_value):
        return self.categorizer.find_keys_by_value(target_value)

    def sorted_summary_df(self):
        lengths = {key: len(value) for key, value in self.categorizer.categories_dict.items()}
        df = pd.DataFrame(lengths.items(), columns=['Category', 'Length'])
        return df.sort_values(by='Length', ascending=False)

    def categorize_all_answers(self, answers):
        for answer_chunk in tqdm(self.chunker.chunk_list(answers), desc="Categorizing answers", unit=" chunk", total=round(len(answers)/self.chunk_size)):
            self.categorizer.categorize_answers(answer_chunk)

    def export_results(self,question):
        exporter = Exporter(self.categorizer, self.answers)
        df_sorted = self.sorted_summary_df()
        exporter.dump_to_excel(df_sorted,question, self.excel_file)
        exporter.plot_result(df_sorted)

    def run(self):
        question, self.answers = self.loader.load_data()
        self.categorize_all_answers(self.answers)
        self.export_results(question)