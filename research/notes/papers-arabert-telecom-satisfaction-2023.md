---
title: "Using the AraBERT Model for Customer Satisfaction Classification of Telecom Sectors in Saudi Arabia"
tags: [arabert, customer-satisfaction, telecom, sentiment, svr-literature]
source_url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC9856834/"
---

# Using the AraBERT Model for Customer Satisfaction Classification of Telecom Sectors in Saudi Arabia

- Authors: Sulaiman Aftan and Habib Shah
- Year: 2023
- Venue: Brain Sciences, volume 13, issue 1, article 147

## What they did

They used sentiment analysis on Arabic tweets to predict customer satisfaction for Saudi telecom companies (STC, Mobily, and ITC). They fine-tuned AraBERT with different activation functions and topologies and compared it against CNN and RNN baselines, as the first application of AraBERT to telecom customer satisfaction prediction in Saudi Arabia.

## Model

AraBERT (fine-tuned, with varied classification-head topologies and activation functions). Baselines: convolutional neural network (CNN) and recurrent neural network (RNN).

## Dataset

AraCust: Arabic tweets about Saudi telecom companies (STC, Mobily, ITC), labeled for customer satisfaction.

## Results

- AraBERT: 94.33 percent accuracy, best of the three methods
- RNN: 91.35 percent accuracy
- CNN: 88.34 percent accuracy
- AraBERT was best in particular on the Mobily and STC datasets

## Lesson for SVR

This is the closest published analogue to our customer_state and churn_risk labels: telecom customer text classified into satisfaction outcomes with an Arabic BERT. Three lessons. First, a fine-tuned Arabic BERT beats CNN and RNN baselines by a clear margin on customer text, which supports our transformer-first approach and gives the team a baseline expectation that a fine-tuned encoder should beat any TF-IDF or RNN model they test. Second, the task here is binary satisfaction, which is much easier than our 9-class complaint categories, so our accuracy will be lower and the comparison to aim for is per-class F1, not their 94 percent headline number. Third, the authors varied the classification head and activation functions, which is a cheap hyperparameter trial for us: the head design on top of the encoder is worth tuning, not just the learning rate.

## Source

https://pmc.ncbi.nlm.nih.gov/articles/PMC9856834/
