#!/bin/bash

# Check if running non-interactively (from Python or environment variable)
if [ ! -t 0 ] || [ "$NON_INTERACTIVE" = "true" ]; then
    NON_INTERACTIVE=true
else
    NON_INTERACTIVE=false
fi

#Check if an image path was provided
if [ $# -eq 0 ]; then
    echo "Error: No image path provided!"
    exit 1
fi

IMAGE_PATH="$1"

#Check if given image file exists
if [ ! -f "$IMAGE_PATH" ]; then
    echo "Error: File '$IMAGE_PATH' does not exist or was not found!"
    exit 1
fi

#Check if zsteg is installed
if ! command -v zsteg &> /dev/null; then 
    echo "Error: zsteg is not installed."
    echo "Please install zsteg using 'gem install zsteg'."
    exit 1
fi

# Function to check if output contains errors
has_errors() {
    local output="$1"
    if [[ "$output" == *"ArgumentError"* ]] || [[ "$output" == *"NoMethodError"* ]] || [[ "$output" == *"comparison of Integer with nil failed"* ]]; then
        return 0  # Has errors
    else
        return 1  # No errors
    fi
}

# Function to run basic zsteg scan
run_basic() {
    echo "Running basic zsteg scan..."
    echo "========================================="
    local output=$(zsteg "$IMAGE_PATH" 2>&1)
    
    if has_errors "$output"; then
        echo "❌ Error: zsteg cannot process this image file."
        echo "This may be due to:"
        echo "  - Corrupted or invalid PNG file"
        echo "  - Unsupported image format"
        echo "  - Missing or malformed image headers"
        echo ""
        echo "Try using a different steganography tool or verify the image file is valid."
    elif [ -n "$output" ]; then
        echo "$output"
    else
        echo "No output from basic scan."
    fi
    echo ""
}

# Function to run verbose scan
run_verbose() {
    echo "Running verbose zsteg scan..."
    echo "========================================="
    local output=$(zsteg -v "$IMAGE_PATH" 2>&1)
    
    if has_errors "$output"; then
        echo "❌ Verbose scan failed - same image parsing error as basic scan."
    elif [ -n "$output" ]; then
        echo "$output"
    else
        echo "No output from verbose scan."
    fi
    echo ""
}

# Function to run detailed scan with all options
run_detailed() {
    echo "Running detailed analysis with all options..."
    echo "========================================="
    local output=$(zsteg -a "$IMAGE_PATH" 2>&1)
    
    if has_errors "$output"; then
        echo "❌ Detailed analysis failed - same image parsing error."
    elif [ -n "$output" ]; then
        echo "$output"
    else
        echo "No output from detailed analysis."
    fi
    echo ""
}

# Function to extract detected data
run_extract() {
    echo "Extracting detected data..."
    echo "========================================="
    
    # First check if basic scan works
    local basic_output=$(zsteg "$IMAGE_PATH" 2>&1)
    
    if has_errors "$basic_output"; then
        echo "❌ Cannot extract data - zsteg cannot parse the image file."
        echo ""
        return
    fi
    
    if [ -n "$basic_output" ] && [[ "$basic_output" != *"no data"* ]]; then
        echo "Available data streams found:"
        echo "$basic_output"
        echo ""
        echo "Attempting to extract common payloads..."
        
        # Try to extract common LSB payloads
        local found_something=false
        for channel in b g r; do
            for bits in 1 2; do
                local payload="${bits}b,${channel},lsb"
                echo "Trying to extract: $payload"
                local extract_result=$(zsteg -E "$payload" "$IMAGE_PATH" 2>&1)
                
                if has_errors "$extract_result"; then
                    echo "❌ Extraction failed for $payload"
                elif [ -n "$extract_result" ] && [[ "$extract_result" != *"Usage:"* ]]; then
                    echo "Extracted from $payload:"
                    echo "$extract_result"
                    echo "---"
                    found_something=true
                fi
            done
        done
        
        if [ "$found_something" = false ]; then
            echo "No data could be extracted using common methods."
        fi
    else
        echo "No extractable data streams detected."
    fi
    echo ""
}

# Function to suggest alternatives
suggest_alternatives() {
    echo ""
    echo "🔧 Alternative Analysis Suggestions:"
    echo "========================================="
    echo "Since zsteg cannot process this image, try these alternatives:"
    echo ""
    echo "1. Check image metadata with exiftool:"
    echo "   exiftool '$IMAGE_PATH'"
    echo ""
    echo "2. Use steghide for JPEG/BMP files:"
    echo "   steghide info '$IMAGE_PATH'"
    echo ""
    echo "3. Try binwalk for embedded files:"
    echo "   binwalk '$IMAGE_PATH'"
    echo ""
    echo "4. Check for trailing data:"
    echo "   strings '$IMAGE_PATH' | tail -20"
    echo ""
    echo "5. Verify the image file is valid:"
    echo "   file '$IMAGE_PATH'"
    echo "   identify '$IMAGE_PATH'"
    echo ""
}

# Function to run all scans
run_all() {
    echo "Running complete zsteg analysis..."
    echo "========================================="
    
    # Test if zsteg can handle the file at all
    local test_output=$(zsteg "$IMAGE_PATH" 2>&1)
    if has_errors "$test_output"; then
        echo "❌ zsteg cannot process this image file due to parsing errors."
        suggest_alternatives
        return
    fi
    
    run_basic
    run_verbose
    run_detailed
    run_extract
}

# Main execution logic
if [ "$NON_INTERACTIVE" = true ]; then
    echo "Running in non-interactive mode..."
    run_basic
    echo "Analysis complete!"
    exit 0
else
    # Interactive mode would go here...
    run_all
fi