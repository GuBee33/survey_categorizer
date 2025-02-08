<script lang="ts">
    import { onMount } from "svelte";

    const API_BASE_URL: string =
        import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";


    let uploadedFileName: string = "";
    let dropdown1Options: string[] = [];
    let dropdown2Options: { [key: number]: string[] } = {};
    let selectedDropdown1: string = "";
    let column_ids: number[] = [];
    let categoriesPerColumn: { [key: number]: string } = {};
    let max_categories_per_answer: number = 1;
    let aggregation_column_id: number | null = null;
    let answer_limit: number | null = null;
    let model_name: string = "gpt-4o";
    let report_file_name: string = "result.xlsx";
    let chunk_size: number | null = 10;

    // New state variable to manage submission state
    let isSubmitting: boolean = false;

    // Fetch existing files on mount and set the first item as selected
    onMount(async () => {
        const res = await fetch(`${API_BASE_URL}/files/`);
        if (res.ok) {
            dropdown1Options = await res.json();
            if (dropdown1Options.length > 0) {
                selectedDropdown1 = dropdown1Options[0];
                await fetchColumns(selectedDropdown1);
            }
        } else {
            const error = await res.json();
            alert(`Failed to load files: ${error.detail}`);
        }
    });

    // Function to fetch columns based on selected file
    const fetchColumns = async (filename: string) => {
        const res = await fetch(
            `${API_BASE_URL}/columns/?filename=${encodeURIComponent(filename)}`,
        );
        if (res.ok) {
            const data = await res.json();
            dropdown2Options = data.columns;
        } else {
            const error = await res.json();
            alert(`Failed to load columns: ${error.detail}`);
        }
    };

    // Handle file upload separately
    const uploadFile = async (event: Event) => {
        const target = event.target as HTMLInputElement;
        const file = target.files ? target.files[0] : null;
        if (file) {
            const formData = new FormData();
            formData.append("file", file);
            const res = await fetch(`${API_BASE_URL}/upload/`, {
                method: "POST",
                body: formData,
            });
            if (res.ok) {
                const data = await res.json();
                uploadedFileName = data.filename;
                // Refresh the dropdown options
                dropdown1Options = await (
                    await fetch(`${API_BASE_URL}/files/`)
                ).json();
                selectedDropdown1 = uploadedFileName;
                dropdown2Options = data.columns;
                alert("File uploaded successfully!");
            } else {
                const error = await res.json();
                alert(`Upload failed: ${error.detail}`);
            }
        }
    };

    const handleSubmit = async () => {
        if (!selectedDropdown1) {
            alert("Please select a file.");
            return;
        }


        const payload = {
            filename: selectedDropdown1,
            column_ids: column_ids,
            categories_per_column_ids: Object.fromEntries(Object.entries(categoriesPerColumn).map(([key, value]) => [key, value.split('\n')])),
            max_categories_per_answer: max_categories_per_answer,
            aggregation_column_id: aggregation_column_id,
            answer_limit: answer_limit,
            model_name: model_name,
            report_file_name: report_file_name,
            chunk_size: chunk_size,
        };

        // Set isSubmitting to true to indicate the submission has started
        isSubmitting = true;

        try {
            const res = await fetch(`${API_BASE_URL}/analize/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = report_file_name.endsWith(".xlsx")
                    ? report_file_name
                    : `${report_file_name}.xlsx`;
                a.click();
                window.URL.revokeObjectURL(url);
                alert("Analysis completed and report downloaded!");
            } else {
                const error = await res.json();
                alert(`Analysis failed: ${error.detail}`);
            }
        } catch (error) {
            alert("An unexpected error occurred.");
        } finally {
            // Reset isSubmitting regardless of success or failure
            isSubmitting = false;
        }
    };
    const clear_categoriesPerColumn=() =>{
        categoriesPerColumn={}
    }
</script>

<div class="max-w-4xl mx-auto p-6 bg-white shadow-md rounded-md">
    <!-- File Upload Section -->
    <div class="flex items-center gap-4 mb-6">
        <div class="flex-1">
            <label for="file-upload" class="block text-gray-700"
                >Upload XLSX File</label
            >
            <input
                id="file-upload"
                type="file"
                accept=".xlsx"
                class="mt-2 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:border
                       file:border-gray-300 file:rounded-md file:text-sm file:font-semibold
                       file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
        </div>
        <!-- Upload Button -->
        <div class="flex-none">
            <button
                class="mt-10 bg-blue-500 text-white py-2 px-6 rounded-md hover:bg-blue-600"
                on:click={uploadFile}
            >
                Upload
            </button>
        </div>
    </div>

    <!-- Main Form Section -->
    <form on:submit|preventDefault={handleSubmit}>
        <!-- Select File -->
        <div class="mb-4">
            <label for="select-file" class="block text-gray-700"
                >Select File</label
            >
            <select
                id="select-file"
                bind:value={selectedDropdown1}
                on:change={() => fetchColumns(selectedDropdown1)}
                class="mt-2 block w-full bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
                <option value="" disabled>Select a file</option>
                {#each dropdown1Options as option}
                    <option value={option}>{option}</option>
                {/each}
            </select>
        </div>

        <!-- <div class="grid grid-cols-2 gap-4"> -->
        <div class="mb-4">
            <label for="column-ids" class="block text-gray-700">
                Select columns for categorization
            </label>
            <div class="mb-4">
                <select
                    id="column-ids"
                    bind:value={column_ids}
                    on:change={clear_categoriesPerColumn}
                    multiple
                    class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                >
                    {#each Object.entries(dropdown2Options) as [key, value]}
                        <option value={key}>{value}</option>
                    {/each}
                </select>
            </div>
        </div>

        {#if dropdown2Options && selectedDropdown1 && column_ids.length > 0}
            <!-- Categories Per Column IDs -->
            <div class="mb-4">
                <label for="col-cat" class="block text-gray-700"
                    >Categories Per Columns</label
                >
                <div
                    class="mt-2 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4"
                >
                    {#each column_ids as id}
                        <div class="flex flex-col">
                            <label
                                for={`category-${id}`}
                                class="block text-gray-600 mb-1"
                            >
                                {#if dropdown2Options[id].length > 15}
                                    {dropdown2Options[id].slice(0, 15)}..
                                {:else}
                                    {dropdown2Options[id]}
                                {/if}
                            </label>
                            <textarea
                                id={`category-${id}`}
                                bind:value={categoriesPerColumn[id]}
                                placeholder="Enter categories (one per line)"
                                class="mt-1 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                            ></textarea>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
        <!-- Aggregation Column ID -->
        <div class="mb-4">
            <label for="aggregation-column-id" class="block text-gray-700">
                Aggregation Column
            </label>
            <select
                id="aggregation-column-id"
                bind:value={aggregation_column_id}
                class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
                <option value="" disabled>Select a column</option>
                {#each Object.entries(dropdown2Options) as [key, value]}
                    <option value={key}>{value}</option>
                {/each}
            </select>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Max Categories Per Answer -->
            <div class="mb-4">
                <label for="max-categories" class="block text-gray-700"
                    >Max Categories Per Answer</label
                >
                <input
                    id="max-categories"
                    type="number"
                    min="1"
                    bind:value={max_categories_per_answer}
                    class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
            </div>

            <!-- Answer Limit -->
            <div class="mb-4">
                <label for="answer-limit" class="block text-gray-700"
                    >Answer Limit</label
                >
                <input
                    id="answer-limit"
                    type="number"
                    bind:value={answer_limit}
                    placeholder="Optional"
                    class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <!-- Chunk Size -->
            <div class="mb-4">
                <label for="chunk-size" class="block text-gray-700"
                    >Chunk Size</label
                >
                <input
                    id="chunk-size"
                    type="number"
                    bind:value={chunk_size}
                    placeholder="Optional"
                    class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
            </div>

            <!-- Model Name -->
            <div class="mb-4">
                <label for="model-name" class="block text-gray-700"
                    >Model Name</label
                >
                <input
                    id="model-name"
                    type="text"
                    bind:value={model_name}
                    class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
            </div>
        </div>

        <!-- Report File Name -->
        <div class="mb-4">
            <label for="report-file-name" class="block text-gray-700"
                >Report File Name</label
            >
            <input
                id="report-file-name"
                type="text"
                bind:value={report_file_name}
                placeholder="result.xlsx"
                class="mt-2 block w-full border border-gray-300 rounded-md p-2 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
        </div>

        <!-- Submit Button -->
        <button
            type="submit"
            class="mt-4 w-full bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 flex items-center justify-center disabled:opacity-50"
            disabled={isSubmitting}
        >
            {#if isSubmitting}
                <span class="spinner"></span>
                Working...
            {:else}
                Submit
            {/if}
        </button>
    </form>
</div>

<style>
    /* Spinner Animation */
    .spinner {
        border: 2px solid rgba(0, 0, 0, 0.1);
        border-left-color: #ffffff;
        border-radius: 50%;
        width: 16px;
        height: 16px;
        animation: spin 1s linear infinite;
        margin-right: 8px;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }
</style>
