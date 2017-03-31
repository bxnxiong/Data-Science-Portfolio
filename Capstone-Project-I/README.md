# About this project
In this project I am trying to answer the following questions: 
1. Is it possible to predict a hit song before it goes into public? 
2. What kinds of features will be most attracting? 
3. Is there a general pattern regardless of time, a formula that can help create a song that is to be a next classic?

The potential client of this project will be songwriters and record companies where managers will decide on how much budget they put into every song based on ‘expected popularity’ of this song. This project, if successfully build a model, can help them with their decision making process.

The data I’m going to use is Million Song Dataset(involving Musixmatch, last.fm and the Echo Nest(now part of Spotify)) from their official website and Billboard chart data I scraped from billboard website and only keep the top 10 songs.

The approach will be, first get 8000 songs from Million Song Dataset(MSD) where half of them will have a top10 ranking from Billboard chart data, then create the target variable by labeling 1 if that song once ranked top10 or 0 has no ranking. Then prepare all possible numeric features from supplementary datasets of MSD, and use classification algorithms like logistic regression(baseline model), random forests and SVM to do prediction. Later in the process, I will add lyrics as bag-of-words form as additional feature and load word2vec model trained using google news to do clustering, and see if within clusters there is a similarity, i.e. whether songs of certain topic is more likely to be popular than others(which intuitively I think there should be).

The final result will be a Jupyter Notebook containing both code and visualizations presenting the findings in this project, and the conclusion whether I succeed in this prediction or not, if yes what will be the limitations, if no what will be the possible reasons why I fail. 

The project, as well as all data and this proposal will be posted in github, under Data-Science-Portfolio/Capstone-Project-I folder.
