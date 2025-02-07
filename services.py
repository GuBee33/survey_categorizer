import os
import json
from tqdm import tqdm
from openai import OpenAI
import pandas as pd
import matplotlib.pyplot as plt
import re

os.environ['OPENAI_API_KEY'] = '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'

class DataLoader:
    def __init__(self, file_path):
        self.df=pd.read_excel(file_path)

    def get_columnIds(self):
        # for index, element in enumerate(self.df.columns):
        #     print(index, element)
        return {index:element for index, element in enumerate(self.df.columns)}

    def get_answers(self,columnId,limit=None):
        question=self.df.columns[columnId]
        return self.df[question].str.replace('\n', '', regex=False).tolist()[:limit]

class Categorizer:
    def __init__(self,model="gpt-4o"):
        self.categories_dict = {}
        self.answers_categories={}
        self.api_client = OpenAI()
        self.model = model

    def categorize_answers(self, question,answers,categories,max_categories_per_answer=3):
        if question not in self.categories_dict:
            self.categories_dict[question]={category: [] for category in categories}
        if f"{question}_2" not in self.answers_categories:
            self.answers_categories[f"{question}_2"]=[]
        for i in range(max_categories_per_answer):
            if f"{question}_category_{i}" not in self.answers_categories:
                self.answers_categories[f"{question}_category_{i}"]=[]
        formatted_answers = "\n".join([f"{i+1}. {answer}" for i, answer in enumerate(answers)])
        system_prompt = (
            "You will receive multiple employee survey responses and a list of existing categories. "
            f"The original questions was: {question}"
            f"For each response, assign up to {max_categories_per_answer} relevant category labels/sentece from the existing categories. "
            "Do NOT use any prefix for the categories like 'new category' os something like this"
            "If none of the existing categories are suitable, you may create a new category, ensuring that the total number of categories does not exceed 30. "
            "Avoid using similar or duplicate categories. "
            "Provide the results as a JSON array, where each element is an array of categories corresponding to each response. "
            "The response must contain only the JSON array with no additional text, markdown formatting, or extra characters. "
            "Use the same language for the category labels/sentece as the language of the survey question."
        )
        existing_categories = [cat for cat in self.categories_dict.get(question, {}).keys() if cat]
        user_prompt = (
            f"Existing categories: [{', '.join(existing_categories)}].\n\n"
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
            self.answers_categories[f"{question}_2"].append(answers[i])
            for j in range(max_categories_per_answer):
                category=None
                if len(categories)>j:
                    category=categories[j]
                self.answers_categories[f"{question}_category_{j}"].append(category)
                if category in self.categories_dict[question]:
                    self.categories_dict[question][category].append(answers[i])
                else:
                    self.categories_dict[question][category] = [answers[i]]

        return self.categories_dict, self.answers_categories

    def find_keys_by_value(self, question,target_value):
        matching_keys = []
        for key, values_list in self.categories_dict[question].items():
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
    def sanitize_string(self,name):
        """
        Sanitize a string to be a valid filename ot sheetname by removing or replacing invalid characters.
        """
        # Define a pattern for invalid filename characters
        invalid_chars = r'[\s<>:"|?*]'
        # Replace invalid characters with underscores
        sanitized = re.sub(invalid_chars, '_', name)
        # Optionally, remove leading/trailing whitespace and dots
        sanitized = sanitized.strip().strip('.')
        return sanitized
    def make_valid_xlsx_filename(self,name):
        """
        Convert a random string to a valid .xlsx filename.
        """
        sanitized = self.sanitize_string(name)
        # Ensure the filename ends with .xlsx
        if not sanitized.lower().endswith('.xlsx'):
            sanitized += '.xlsx'
        return sanitized

    def dump_to_excel(self, dfs ,excel_file='result_data.xlsx'):
        excel_file=self.make_valid_xlsx_filename(excel_file)
        with pd.ExcelWriter(excel_file) as writer:
            for sheetname,df in dfs.items():
                df.to_excel(writer, sheet_name=self.sanitize_string(sheetname), index=False)
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
    def __init__(self, file_path,model="gpt-4o",result_excel='result_data.xlsx',answer_limit=None,chunk_size=10):
        self.loader = DataLoader(file_path)
        self.answer_limit=answer_limit
        self.categorizer = Categorizer(model)
        self.chunker = Chunker(chunk_size)
        self.excel_file = result_excel
        self.chunk_size=chunk_size
        self.dfs_2_excel={}

    def find_keys_by_value(self, target_value):
        return self.categorizer.find_keys_by_value(target_value)

    def sorted_summary_df(self):
        lengths = {key: len(value) for key, value in self.categorizer.categories_dict.items()}
        df = pd.DataFrame(lengths.items(), columns=['Category', 'Length'])
        return df.sort_values(by='Length', ascending=False)

    def categorize_all_answers(self, question,answers,categories,max_categories_per_answer):
        for answer_chunk in tqdm(self.chunker.chunk_list(answers), desc=f"Categorizing answers for {question[:15]}...", unit=" chunk", total=round(len(answers)/self.chunk_size)):
            self.categorizer.categorize_answers(question,answer_chunk,categories,max_categories_per_answer)

    def export_results(self):
        exporter = Exporter()
        exporter.dump_to_excel(self.dfs_2_excel, self.excel_file)
        # exporter.plot_result(df_sorted)

    def aggregate_categories(self,column_id_of_question,column_id_of_aggregate_by_id,number_of_max_categories):
        question=self.loader.df.columns[column_id_of_question]
        aggregate_by=self.loader.df.columns[column_id_of_aggregate_by_id]
        categories=[f"{question}_category_{i}" for i in range(number_of_max_categories)]
        stat_df_groupby= self.loader.df.melt(id_vars=[question, aggregate_by], value_vars=categories,
                        var_name='CategoryType', value_name='Category').drop('CategoryType', axis=1).groupby([aggregate_by,'Category']).count().reset_index().sort_values([aggregate_by,question],ascending=False)
        stat_df=stat_df_groupby.groupby("Category")[question].sum().reset_index().sort_values(question,ascending=False)
        return {f"{question[:15]}_{column_id_of_question}_stat_groupby":stat_df_groupby,f"{question[:15]}_{column_id_of_question}_stat":stat_df}

    def run(self,columnIds,categories_per_columnId,max_categories_per_answer,aggregation_column_id=None):
        for columnId in columnIds:
            question=self.loader.df.columns[columnId]
            self.answers = self.loader.get_answers(columnId,self.answer_limit)
            self.categorize_all_answers(question,self.answers,categories_per_columnId[columnId],max_categories_per_answer)
        self.loader.df=pd.concat([self.loader.df,pd.DataFrame(self.categorizer.answers_categories)],axis=1)
        self.dfs_2_excel = self.dfs_2_excel | {"rawdata":self.loader.df}
        
        if aggregation_column_id:
            for columnId in columnIds:
                self.dfs_2_excel = self.dfs_2_excel | self.aggregate_categories(columnId,aggregation_column_id,max_categories_per_answer)
        self.export_results()