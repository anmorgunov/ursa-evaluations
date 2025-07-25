#!/bin/bash

mkdir -p data/models/dms/checkpoints

# Define URLs
CKPT_URL="https://files.batistalab.com/DirectMultiStep/ckpts"
DATASET_URL="https://files.batistalab.com/DirectMultiStep/datasets"

# Model checkpoint configurations
model_names=(
    "Flash"
    "Flex"
    "Deep"
    "Wide"
    "Explorer"
    "Explorer-XL"
    "Flash-20"
)
model_info=(
    "flash.ckpt|38"
    "flex.ckpt|74"
    "deep.ckpt|159"
    "wide.ckpt|147"
    "explorer.ckpt|74"
    "explorer_xl.ckpt|192"
    "flash_20.ckpt|74"
)

# Download model checkpoints
read -p "Do you want to download all model checkpoints? [y/N]: " all_choice
case "$all_choice" in
    y|Y )
        for i in "${!model_names[@]}"; do
            model="${model_names[$i]}"
            info="${model_info[$i]}"
            IFS="|" read -r filename size <<< "$info"
            echo "Downloading ${model} model ckpt (${size} MB)..."
            curl -o "data/models/dms/checkpoints/${filename}" "${CKPT_URL}/${filename}"
        done
        ;;
    * )
        for i in "${!model_names[@]}"; do
            model="${model_names[$i]}"
            info="${model_info[$i]}"
            IFS="|" read -r filename size <<< "$info"
            read -p "Do you want to download ${model} model ckpt? (${size} MB) [y/N]: " choice
            case "$choice" in
                y|Y )
                    curl -o "data/models/dms/checkpoints/${filename}" "${CKPT_URL}/${filename}"
                    ;;
                * )
                    echo "Skipping ${model} ckpt."
                    ;;
            esac
        done
        ;;
esac

# Download canonicalized eMols, buyables, ChEMBL-5000, and USPTO-190
read -p "Do you want to download canonicalized eMols, buyables, and target datasets? (244 MB) [y/N]: " choice
case "$choice" in
    y|Y )
        echo "Downloading canonicalized eMols, buyables, ChEMBL-5000, and USPTO-190 ..."
        wget -O "data/models/dms/compounds.zip" "https://figshare.com/ndownloader/files/53117957"
        (cd data/models/dms && unzip -o compounds.zip && rm compounds.zip)
        ;;
    * )
        echo "Skipping canonicalized eMols and buyables."
        ;;
esac