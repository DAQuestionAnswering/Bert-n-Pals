#!/usr/bin/env bash

for source_task in 'multinli'; # 'snli' 'mnli' 'mnli' 'qnli' 'qqp' 'msmarco'
 do
    for target_task in 'snli' 'mnli' 'wikiqa' 'scitail'; # 'snli' 'mnli' 'qnli' 'qqp' 'msmarco' 'scitail' 'wnli' 'rte' 'mrpc' 'wikiqa'
     do
        if [ $source_task = $target_task ];
        then
            continue
        else
            if [ $target_task = 'snli' -o  $target_task = 'mnli' -o  $target_task = 'qnli' -o  $target_task = 'qqp' -o  $target_task = 'msmarco' ]
            then
                a="2e-5"
            else
                a="1e-5 2e-5 3e-5 4e-5"
            fi
            for lr in $a;
            do
            echo " ##### Training $target_task  task from ${source_task} ckpt with $lr #### "
            python train_nli.py \
                        --vocab_file uncased_L-12_H-768_A-12/vocab.txt \
                        --bert_config_file configs/bert_config.json \
                        --init_checkpoint saved_test_nli/${source_task}100k_bert_config/best_model.pth \
                        --output_dir saved_test_nli \
                        --tasks ${target_task} \
                        --do_lower_case \
                        --do_train \
                        --do_eval \
                        --learning_rate $lr \
                        --max_seq_length 128 \
                        --train_batch_size 32 \
                        --data_dir ../match_dataset/ \
                        --sample prop \
                        --source ${source_task} \
                        --num_train_epochs 3 ;
            done
#            fi
        fi
     done
 done
