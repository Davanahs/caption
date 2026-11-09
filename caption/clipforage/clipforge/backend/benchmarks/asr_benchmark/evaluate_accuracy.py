"""
ClipForge ASR Benchmark — Fast & Standard Accuracy & Alignment Engine
Uses jiwer for standard WER/CER calculation and difflib for word-by-word alignment.
"""

import os
import json
import re
import difflib
import jiwer
import numpy as np

BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")

# ---------------------------------------------------------
# 1. Human-Verified Reference Transcripts
# ---------------------------------------------------------

REF_VIDEO2 = (
    "So whether you've landed on this video because someone suggested a podcast to you and you weren't "
    "quite sure what they were talking about or you've heard about a ton of people starting podcasts and "
    "you want to know if that's something that you'd be into, whatever your reason, welcome. We'd love "
    "to help you understand what a podcast is and how they work. "
    "So what is a podcast? A podcast is essentially a series or collection of digital audio files that "
    "are made available for listening or downloading via the internet. So that could be a website. It "
    "could be a listening app. What have you. And so each individual audio file that is uploaded would "
    "be considered a podcast episode. And podcasts are typically hosted by a person that leads a "
    "conversation that will tell stories that may report on the news and they are called a podcast "
    "host. A person who creates a podcast is called a podcaster. "
    "The best way to think of podcasting is kind of like the Netflix of audio. So you know how you can "
    "pick a show on Netflix and just watch the whole show or just watch a few episodes. Podcasting is "
    "very similar. You can pick a show and decide you want to listen to all the episodes they have "
    "available or you can just listen to one or two of the episodes that they have available. The thing "
    "is this is audio on your time. "
    "So how do podcasts work? Well if you were to create a podcast you'd upload audio, get a hosting "
    "site to make it available. And when you do that, your hosting site would create an RSS feed. And "
    "that just stands for Real Simple Syndication. All this is is a page of raw data that holds all "
    "the information about your podcast. Its title, the cover art, how many episodes, title episodes, "
    "the whole shebang. "
    "So where can you listen to these things? Podcasts. You can listen to podcasts in a couple of "
    "different places. So there are podcast listening apps. We like to call some of them directories. "
    "Apple Podcasts is one such. Google Podcasts is another directory, but you can also listen to podcasts "
    "in a lot of music listening apps. So Spotify has made podcasts available in their app, Amazon, "
    "Stitcher is a podcast specific app that you can listen to podcasts on. Some people even have their "
    "podcasts embedded on their website. So there are embedded players where you can listen to podcasts "
    "that aren't necessarily in a directory. "
    "And if you are a Buzzsprout user, we actually give you a podcast listening website all your own "
    "for your podcast. So people can listen there as well. "
    "So now that you know what a podcast is, if you're interested in starting a podcast, check this "
    "video out over here that's going to give you all the information that you need to know to start a "
    "podcast. We hope this video answered your questions about what a podcast is. As always thanks for "
    "watching and keep podcasting."
)

REF_VIDEO1 = (
    "I gave two AI models the hardest test that I could think of. I tested everything from cinematic "
    "videos to product videos to actually giving my actual face and asking them to create a jungle fight "
    "scene. And honestly some of the results actually surprised me. One of the models handled things I "
    "expected it to mess up. And the other model actually started falling apart at places which I did not "
    "expect. On one side we have Wan 2.1 and on the other side we have Seedance 2.0. Same prompts, same "
    "platform, same tests with no cherry picking and no second attempts. By the end of this video you "
    "will actually know which model performs best at which cases, where it actually breaks and you will "
    "also be able to understand which model actually makes sense for your workflow. Quick disclosure "
    "before we start the video, this video is actually sponsored by TopView. But the test itself is "
    "completely real. I ran both the models myself. You will see actual results and I will be honest "
    "about what worked and what did not. Hi guys, I am Nishant Chahar. I am an ex-Microsoft software "
    "engineer. I have built and sold my first startup, raised around 250k USD for my second startup and "
    "I am building multiple products right now. You can check out all of them, the link to those are in "
    "the description. Before we start testing the results, let's first understand what are these two "
    "models because they actually come from different companies and were actually built for slightly "
    "different priorities. And you will be able to see the difference by the actual output that I will be "
    "showing you on what the priorities were and how they are different and for which use case which "
    "model is better. So Wan 2.1 comes from Alibaba. It is more of a reliable, cost effective and an "
    "all-rounder that does a good job of following your prompts and handling realistic shots, especially "
    "when it comes to products and real world scenes. The second one is Seedance 2.0. This one comes from "
    "ByteDance, the parent company of TikTok if you don't know. It leans more towards the cinematic "
    "output with a stronger focus on lighting, mood and storytelling. So if I had to simplify, Wan is a "
    "dependable workhorse, while Seedance is more sort of a filmmaker. Now let's see how much of this "
    "actually stands when we are building things. So first let me show you where we are doing this. I will "
    "go to TopView AI, sign in with my Google account and I'll land on this particular dashboard. From here "
    "I'll open board workspace. This is the main screen we'll be working on. And here's why I'm actually "
    "using TopView for this. Look at the model panel. It has both the models we are testing today sitting "
    "right here along with a bunch of others as well, all under a single subscription. So I can run this "
    "test with the same prompt through each one without changing anything and I will actually get a fair "
    "comparison instead of jumping between two different websites. The workflow is pretty straightforward. "
    "For both models you pick the model, type in your prompt, set the aspect ratio, duration and resolution "
    "and then hit generate. We'll keep all of these settings the same for both the videos so the comparison "
    "is fair. And to make this test actually useful we'll judge both the models on four things that actually "
    "matter: how well they follow the prompt, how good the final output looks like, how natural the motion "
    "feels, and how well they handle fine details. With that let's run the first test. So for the first "
    "test I want to start with something cinematic that actually pushes both the models. So let's go with a "
    "proper moody and atmospheric shot. So I'm going to paste the exact same prompt for both the models and "
    "see how they handle it. Let me first get the prompt from here and let's generate the first one. So we "
    "have added the prompt, a 30 second photorealistic sequence, character Maya. We have added all the prompts "
    "and this is what it is generated. I'll show you. That is like looks good. So for this one we are using "
    "Seedance 2.0. So this output was from Seedance 2.0. It asked me a bunch of questions after I added the "
    "prompt and finally we had this final video. Let's go and check out the other video that was generated "
    "using Wan. So this video was generated using Wan. We added the same prompt as you can see. It also asked "
    "me to do the same thing and finally we have the final output. Let me show this to you. So as you can "
    "see there were a few misses. The packet was much bigger but actually it was just a note which came out "
    "of it. But the characters were pretty consistent throughout the video that was generated using Wan as you "
    "can see. And even the background music, the background characters, all of them look really real. Right? "
    "And this was the old one. Let's compare them side by side. For the first one that was generated using "
    "Seedance, as you can see the kurta is not actually red and that was the first instruction that we gave, "
    "red kurta long braid. I actually like Wan one much better because as you can see it was a proper cafe "
    "scene. There were so many people behind it as well. And the details, the character, the prompts that I "
    "gave with the clear details, all of them were properly shown in that one. So this one goes to Wan for sure. "
    "Most of you are going to use this for product videos, ads, etc., and not for short films. Now when you are "
    "building a product video the challenge is totally different. Here it's not about the character or the "
    "story or the colors. It's more about the product that you are giving it is consistent throughout all the "
    "videos. So for the next round let's see how they actually perform for product showcase video. I'll use the "
    "same prompt and generate one video with Wan and the other one using Seedance. Let's compare both. This one "
    "was done using Wan. Let me show you the Seedance video as well. Har khushi thodi aur meethi, asli doodh, "
    "asli chocolate, ek bite aur mood set. Aaj kuch meetha ho jaye. So I genuinely liked the Wan video and this "
    "one as well as you can see it showcasing the proper product. It was also showing all the details, the "
    "sound behind it actually matched everything. The voiceover was also very crisp and clean. So this one "
    "also goes to Wan like being actually really honest. Now it's time for the round 3. This one is the most "
    "difficult one. Here I am the main character and the prompt is more around me being in a jungle fight. So "
    "let's see how this one goes. So I've pasted the prompt, I have given all the things. Now it will ask me "
    "a few questions. Once that is done we will have our final video ready for Wan. We have the Wan video with "
    "us. Galti kardi mujhe chhedke, agar pakadna hai toh aur tezi se bhaago. It has messed up my face a bit "
    "honestly and it was decent, like I would not rate it a lot. Now let's compare it with the Seedance one. "
    "This one has given more facial consistency for sure. Agar pakadna hai toh aur tezi se bhaago. I think for "
    "this one I will give it to Seedance for sure. As we even discussed in the start of the video, if you are "
    "making a cinematic film or short film, Seedance is better than Wan. But in your general day to day case "
    "here the facial consistency in Wan is not that great and all the other characters also it created like "
    "very similar to my face. But Seedance did a better job here for sure. So if you are making cinematic "
    "videos, storytelling content or moody ads where lighting, atmosphere and overall looks actually matter, "
    "then Seedance is a better model for you. But if you are making product videos, e-commerce ads, explainer "
    "videos or social content where consistency, prompt accuracy and clean output matters more, then you "
    "should definitely use Wan. So I wouldn't say one is better than the other one, both have their pros and "
    "cons. You should use the one that actually helps you out in your particular case. Both of them are "
    "better at different types of videos. And there is one more thing that can actually change your perspective: "
    "the cost. On TopView's Ultra plan, Seedance costs around 3.6 dollars for a 30 second video while Wan costs "
    "around 1.2 for the same 30 second video, which is almost one by three of the price or one third the price. "
    "So if price is a concern I think Wan did a really good job overall like in all the 3 tests. It actually was "
    "better in the first two, but it was not that good on the third one. It had the facial consistency, but when "
    "you are uploading the character maybe it can improve. So the choice is yours, the price is much much less "
    "for Wan. So Wan would cost you one third as much and you also get 365 days of unlimited use compared to 60 "
    "days for Seedance. Here you can use unlimited like Wan with TopView Ultra annual plan. So Seedance will "
    "give you more cinematic results, but Wan will get the job done at one third of the cost. And the real "
    "question is do you want to pay that extra amount for the extra polish or for most of the cases it doesn't "
    "matter. For a filmmaker maybe that is the case, but if you are not creating a film then using a cheaper "
    "model which does 70 to 80% of the job or even 90 at cases is a better choice. Both the models are "
    "available on TopView right now if you want to try it out, the link is in the description. Do let me know "
    "in the comments section which one do you want to pick and do let me know what other videos do you want "
    "to see on this channel. Thank you so much, see you in the next one."
)

REF_VIDEO3 = (
    "Last month I almost cancelled my Anthropic subscription and I am paying $200 per month for that. And "
    "it's not that I've recently started paying for Claude, I've been paying for Claude for more than one year "
    "now. And it's not like I suddenly stopped using AI. But I've started using AI more and more for more things "
    "that are mundane and monotonous for me. I've started automating everything and anything that I can find. "
    "I use it for coding, research, video editing, graphic designing and a lot more. And also sometimes for very "
    "simple work, I just give Claude Cowork access to my desktop and ask it to do things which I don't want to "
    "because I'm just lazy. And the reason why I was cancelling my Claude subscription was because of a Chinese "
    "model called Kimi. Kimi is making waves outside. If you might have seen the launch, if you might have seen "
    "Twitter, Reddit, everyone is talking about Kimi everywhere. So I was just asking myself a very simple "
    "question: is it even worth paying $200 a month if a free model can do something similar to that? Honestly, "
    "I tried out Kimi for a few things and we are going to test the free version of Claude, the paid version of "
    "Claude as well as the free version of Kimi because I don't have the option to upgrade Kimi to a pro version "
    "because it's just asking me to join the waitlist. But we'll first design a website, we will create a 3D "
    "model of something to actually test out the different features that we have. If you want a more detailed "
    "in-depth comparison between Kimi Claude, Kimi Work or Kimi Code with Claude or Codex, do let me know in the "
    "comments section and we'll make a video on those two. By the end of this video, you will have an answer to "
    "the question that whether a cheaper model can do your daily tasks, the daily things that you pay $20 or "
    "$200 per month on. If yes, then why not just use this one? Hi guys, I'm Nishant Chahar. I work with AI "
    "for a living. I used to work at Microsoft, left that, sold my first company, now I'm building another AI "
    "company where I've raised $250k in the first round of funding and we are building a lot of products now. "
    "If you want to check out a few of our products, the links to them are in the description. There's Miles, "
    "there's HackIt, there's Scout, try out whichever you like. So before we start, just like the video, "
    "subscribe to the channel, it helps me give some motivation to create more such content and without any "
    "further ado let's start the video. But first of all the question that comes to your mind is what exactly "
    "is Kimi? So to answer that, if you know OpenAI has ChatGPT, Anthropic has Claude, similarly Moonshot AI is "
    "the company behind Kimi. For normal conversations you have Kimi Chat. For Cowork-like tasks or Codex-like "
    "tasks you have Kimi Work. Similarly like Claude Design you have Kimi Design and like Claude Code or Codex "
    "you have Kimi Code. So every product that is out there by these frontier labs you have a similar version "
    "of that by Moonshot AI as well. There is one more product, if you have used Hermes Agent or if you have "
    "used OpenClaude, there is Kimi Claw as well which can do a lot of your tasks. Also how Kimi is different "
    "from all these models? Not technically, Kimi K3 is a very huge model. But you actually don't need to "
    "understand the engineering behind it. I will try to explain to you what exactly is Kimi K3 in simpler "
    "terms. So Kimi uses something called mixture of experts system. So just imagine it like that: you have a "
    "company of hundreds of employees. Some employees are good at something, some employees are good at "
    "something else. For example you have few employees which are good at design, some are good at sales, some "
    "are good at marketing, some are good at product, some are good at coding. So you have different types of "
    "employees. Now you are building a product, you might not need a sales guy in that meeting when you are "
    "actually building it. You will need the marketing and sales people when you are selling something or "
    "thinking about the marketing of that particular product. Or you give a company a coding problem, you won't "
    "find a non-tech guy, a salesperson or marketing person for that coding problem. So Kimi also roughly works "
    "like that. It has huge capabilities, but when you give it a task it decides which of these capabilities "
    "do I actually need for this task. It also has a very large context window. To understand what a context "
    "window is, context window is the amount of information that an AI model can actually store while it is "
    "working and it doesn't forget about it. So if you want to learn about all these basic terms, I created a "
    "video on basics of AI. The video will be in the i-button, you can definitely check that out. We have "
    "talked about everything. We have also talked about the basic tools like Claude Chat, Claude Code. We have "
    "also talked about all these terms that you listen to every single day so that when you are in these "
    "conversations you don't sound dumb. So do check it out. So if the context window is very small what "
    "happens is you cannot give it a large video or a large document. Initially Google did the same thing when "
    "Google launched their Gemini models. I think the Gemini 1.5 model, they increased the context window to I "
    "think 1 million tokens. So a lot of information was being stored in the chat itself. So if you uploaded a "
    "long PDF it can actually store that inside the chat itself and it will remember and actually give you "
    "answers according to that. Before that it was not possible. There is one thing that makes Kimi different "
    "from your Claude: that is Kimi is open weights. So what does that mean? Open weights means that you can "
    "actually download that model and run it yourself. You can run it in your system, but you cannot run it "
    "on your laptop because it doesn't have the compute required. But if companies have data centers and their "
    "own compute they can actually download the model and run it on their own system. They don't need to pay for "
    "the cloud or pay for the subscription. But now if you understand all this, let's now directly move to "
    "actually using both Claude and Kimi. Let's go. You just need to type kimi.ai and you'll land on this page. "
    "It shows me I can upgrade the plan, but unfortunately I cannot as you can see. It just asks me to join "
    "the waitlist. So we cannot test a lot of the things because we just have the free version. I've logged into "
    "both Kimi and Claude for the free version. You can see this is the first time I'm using this account. As you "
    "can see, I have started using the free version and we will test it out. You just need to log in with your "
    "Gmail ID or whatever email that you use. Once you log in, you will land up on this page. The whole "
    "interface will look very familiar because this is very similar to Claude or ChatGPT if you have used. As "
    "you can see here you have the text box where you will enter your prompt and then Kimi. I think the penguin "
    "is the mascot, penguin is Kimi here. So Kimi will code things for you, do the things for you whatever you "
    "ask it to do. If you check here there is an option to download the Kimi app as well on your Mac or Windows. "
    "Now if you see there is an option to select the model: you can select K3, you can select K3 Swarm or you "
    "can select Instant and you can also select the standard which is your high or low. There are some of the "
    "things which people have built using Kimi. If I want a simple answer I'll just use Instant. If I want a "
    "more in-depth research or something like that I'll then use K3. And if I have a multi-agent task then I'll "
    "use K3 Swarm. So there are multiple options as you can see here. We'll talk about all these one by one so "
    "that you understand which one is for what. You can read and also understand. So the Swarm is for multi-agent "
    "work. So if you have anything that needs multiple agents, maybe it's creating a website with code review "
    "or building a game, you can actually use Swarm. Then you have slides, second is slides. You can use to "
    "build beautiful slides. A lot of people actually got to know about Kimi because people started using this "
    "and comparing it with Gamma and it actually builds really good slides, you can check out. Then is your "
    "deep research, it is similar to other deep research whether you check out Claude, ChatGPT, Perplexity, "
    "you find deep research everywhere. Next is your website, you can create websites using this one. Next is "
    "docs, creating beautiful docs, either it's PDF or a doc. You can use this to build the same. Then there "
    "is sheets, sheets can do mathematical calculations, if you have an Excel or CSV, you want to get insights "
    "from that you can use this one. Then you have design, which is similar to Claude Design, then Kimi Work, "
    "which is very similar to your Claude Cowork or Codex, then you have Kimi Code and Kimi Claw. So Kimi Claw "
    "is I think one of the most interesting ones, it is very similar to Hermes Agent, we recently made a video "
    "on that too, if you haven't checked out do check it out. And don't forget to subscribe for more such amazing "
    "videos, do let me know what do you want me to create content on, I will do that for you. As you can see "
    "here there is plugins and skills that you can add, multiple plugins and skills. These are all the installed "
    "skills like image generation, audio generation, international organizations, SEC, global blah blah blah. "
    "These are all the plugins that you can find. And here you can find all the skills. If you already have some "
    "skills that you want to add you can add or you can just use the skills which are available here. As you "
    "can see there is equity research, humanizer, copywriting, ad creatives, content research writer, etc. etc. "
    "So you can add skills and plugins very similar to what you do in Claude Code, Claude or ChatGPT. These "
    "features are exactly same. We are not going to cover these three. If you want a separate video comparing "
    "these with Claude Code or Codex, do let me know, we will make that. Now we will be doing two tasks, the "
    "first task is building a website. We will be using Claude and Kimi, the free versions, and then we will "
    "compare which one is better. We will just paste the prompt, we will give the same prompt to both Claude "
    "and wait wait wait wait wait wait wait. We will use the best model so we cannot use... We will use Sonnet "
    "in this and we will also try the same thing with Opus, that is when we will be actually able to compare it "
    "with Kimi K3. The first test I just wanted to do something which anyone can judge, so I decided to create "
    "a website. For after seeing a website people can tell whether the website looked good or not and you don't "
    "need technical skills to judge a website. And the end user is going to be a normal user who is understanding "
    "like who's checking out the website. So I feel this was the best test that we can do. You can see both of "
    "them are using Opus is asking us some questions, Sonnet did not ask us any questions. Opus asked us a lot "
    "of questions because in the settings I have added to ask clarifying questions. So this is one of the "
    "instructions that I have added in Claude, so whenever I give it a task it mostly asks me questions around "
    "that task before actually starting to work on that task. So yeah that is one thing I have done. This does "
    "not look bad at all. So when we created this website we did not use Figma, we did not use any designer, "
    "we just used these two AI tools. So I ran it with the free version as well and the paid version as well. "
    "So for the free version when I added the first prompt for Claude my limit was exhausted. But for Kimi I "
    "was able to get both the tests done. So what I did is I also used my pro subscription and Opus 3.5 to "
    "actually build the same two websites because there we were using Kimi K3 which is equivalent to Opus 3.5 "
    "and not Sonnet. But there is important part: some of the features that we talked about are not actually "
    "available in the free version of Kimi. The Kimi Work, the Kimi Claw, all of them are not available in the "
    "free version, so you need to upgrade that. I was seeing the join waitlist option, I have already joined the "
    "waitlist. As soon as I get the premium version I will definitely create a video on that as well by actually "
    "taking the subscription. If you want that video do let me know in the comment section. Now Kimi K3 is also "
    "available through the API. You can use the API to actually use Kimi in Claude Code or different other "
    "coding tools where you can run free models. But here also if you use Kimi K3 the price is quite high: "
    "so it is $3 per 1 million input tokens and $15 per 1 million output tokens, comparing it to Claude. "
    "Claude Opus is around $5 per million tokens for input and $25 per million tokens for output. So it is "
    "actually a little more expensive than your Kimi. I also saw a post on Twitter or LinkedIn where someone "
    "tested this out: it actually took the same amount of tokens because the token pricing is basically "
    "different, but it takes twice the amount of tokens to do the same task. Someone actually ran that "
    "experiment, so that's why it in turn costs you more than Opus 3.5. So after testing it out I would say "
    "if you can use a paid version I would definitely highly recommend you to use either Claude, ChatGPT or "
    "Gemini. I think Gemini is a good option because if you are a student or if you are in India, if you have a "
    "Jio SIM you can get Gemini Pro for free for around 1 to 1 and a half years. That is a lot. I am also "
    "using Gemini for a lot of the tasks, I have the free version and you also get some storage as well. So "
    "definitely use a paid version, it is always better than the free one. And if you cannot, then you have "
    "so many free options right now, combine capabilities of all of those and use whichever you want to use. "
    "So yeah that was it for this video. If you want me to make more such videos do let me know in the comments "
    "section. Thanks so much for watching, see you in the next one. Bye."
)

REFERENCES = {
    "video1": REF_VIDEO1,
    "video2": REF_VIDEO2,
    "video3": REF_VIDEO3
}

# ---------------------------------------------------------
# 2. Text Normalization and Alignment Utilities
# ---------------------------------------------------------

def normalize_text(text: str) -> str:
    """Standard ASR normalization: lowercase, strip punctuation, normalize whitespace."""
    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize(text: str):
    return text.split()

def align_words_sequence_matcher(ref_words, hyp_words):
    """
    Fast sequence matcher alignment between reference tokens and hypothesis tokens.
    Returns (ref_map, hyp_map, stats)
    ref_map maps ref_idx to (hyp_word_or_eps, op)
    """
    matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
    ref_aligned = [("<eps>", "D")] * len(ref_words)
    
    s_count, d_count, i_count, c_count = 0, 0, 0, 0
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx, r_i in enumerate(range(i1, i2)):
                h_j = j1 + idx
                ref_aligned[r_i] = (hyp_words[h_j], "C")
                c_count += 1
        elif tag == "replace":
            # Overlapping substitution
            ref_len = i2 - i1
            hyp_len = j2 - j1
            for k in range(max(ref_len, hyp_len)):
                if k < ref_len and k < hyp_len:
                    ref_aligned[i1 + k] = (hyp_words[j1 + k], "S")
                    s_count += 1
                elif k < ref_len:
                    ref_aligned[i1 + k] = ("<eps>", "D")
                    d_count += 1
                else:
                    i_count += 1
        elif tag == "delete":
            for r_i in range(i1, i2):
                ref_aligned[r_i] = ("<eps>", "D")
                d_count += 1
        elif tag == "insert":
            i_count += (j2 - j1)
            
    return ref_aligned, s_count, d_count, i_count, c_count

def evaluate_technical_vocabulary(ref_text, hyp_text, tech_terms):
    norm_hyp = normalize_text(hyp_text)
    details = {}
    correct = 0
    total = len(tech_terms)
    
    for term in tech_terms:
        norm_term = normalize_text(term)
        found = norm_term in norm_hyp
        details[term] = {
            "expected": term,
            "found": found
        }
        if found:
            correct += 1
            
    acc = (correct / total) * 100.0 if total > 0 else 0.0
    return correct, total, acc, details

def evaluate_numbers(ref_text, hyp_text, expected_numbers):
    norm_hyp = normalize_text(hyp_text)
    details = {}
    correct = 0
    for num in expected_numbers:
        norm_num = normalize_text(num)
        found = norm_num in norm_hyp
        details[num] = {"expected": num, "found": found}
        if found:
            correct += 1
    acc = (correct / len(expected_numbers)) * 100.0 if expected_numbers else 0.0
    return correct, len(expected_numbers), acc, details

# ---------------------------------------------------------
# 3. Execution & Report Generation
# ---------------------------------------------------------

def main():
    print("="*70)
    print("RUNNING DETAILED ASR ACCURACY & ALIGNMENT EVALUATION")
    print("="*70)

    # Save human reference files
    for vid_key, ref_str in REFERENCES.items():
        ref_path = os.path.join(RESULTS_DIR, f"reference_{vid_key}.txt")
        with open(ref_path, "w", encoding="utf-8") as f:
            f.write(ref_str)
        print(f"[Reference] Saved reference_{vid_key}.txt ({len(tokenize(ref_str))} words)")

    TECH_VOCAB = {
        "video1": [
            "AI", "Wan", "Seedance", "TopView", "Nishant", "Alibaba", "ByteDance",
            "TikTok", "Google", "photorealistic", "Maya", "kurta", "prompt", "duration",
            "resolution", "product", "e-commerce", "cinematic"
        ],
        "video2": [
            "podcast", "podcasting", "podcasts", "podcaster", "audio", "Netflix",
            "RSS", "feed", "Syndication", "Apple", "Google", "Spotify", "Amazon",
            "Stitcher", "Buzzsprout", "directory"
        ],
        "video3": [
            "Anthropic", "Claude", "Cowork", "Kimi", "Moonshot", "ChatGPT", "OpenAI",
            "Codex", "Hermes", "mixture of experts", "context window", "Gemini", "tokens",
            "open weights", "compute", "Swarm", "Gamma", "Perplexity", "Sonnet", "Opus", "Figma", "Jio"
        ]
    }

    NUMBERS = {
        "video1": ["two", "250k", "30 second", "3.6", "1.2", "one third", "365 days", "60 days", "70", "80", "90"],
        "video2": ["one", "two", "raw data"],
        "video3": ["200", "one year", "20", "250k", "1 million", "3", "15", "5", "25", "twice"]
    }

    all_evaluations = {}
    combined_stats = {
        "whisper": {"words_ref": 0, "s": 0, "d": 0, "i": 0, "c": 0, "chars_ref": 0, "char_s": 0, "char_d": 0, "char_i": 0},
        "whistle": {"words_ref": 0, "s": 0, "d": 0, "i": 0, "c": 0, "chars_ref": 0, "char_s": 0, "char_d": 0, "char_i": 0},
        "whistle_biased": {"words_ref": 0, "s": 0, "d": 0, "i": 0, "c": 0, "chars_ref": 0, "char_s": 0, "char_d": 0, "char_i": 0}
    }

    side_by_side_tables = {}

    for vid_key in ["video1", "video2", "video3"]:
        print(f"\n--- Evaluating {vid_key} ---")
        ref_text = REFERENCES[vid_key]
        norm_ref = normalize_text(ref_text)
        ref_tokens = tokenize(norm_ref)
        num_ref_words = len(ref_tokens)
        num_ref_chars = len(norm_ref)

        with open(os.path.join(RESULTS_DIR, f"whisper_{vid_key}.txt"), "r", encoding="utf-8") as f:
            whisper_raw = f.read()
        with open(os.path.join(RESULTS_DIR, f"whistle_{vid_key}.txt"), "r", encoding="utf-8") as f:
            whistle_raw = f.read()
        with open(os.path.join(RESULTS_DIR, f"whistle_biased_{vid_key}.txt"), "r", encoding="utf-8") as f:
            whistle_biased_raw = f.read()

        norm_whisper = normalize_text(whisper_raw)
        norm_whistle = normalize_text(whistle_raw)
        norm_whistle_biased = normalize_text(whistle_biased_raw)

        whisper_tokens = tokenize(norm_whisper)
        whistle_tokens = tokenize(norm_whistle)
        whistle_biased_tokens = tokenize(norm_whistle_biased)

        # Use jiwer for gold-standard word error rate & char error rate
        w_word_out = jiwer.process_words(norm_ref, norm_whisper)
        wh_word_out = jiwer.process_words(norm_ref, norm_whistle)
        whb_word_out = jiwer.process_words(norm_ref, norm_whistle_biased)

        w_char_out = jiwer.process_characters(norm_ref, norm_whisper)
        wh_char_out = jiwer.process_characters(norm_ref, norm_whistle)
        whb_char_out = jiwer.process_characters(norm_ref, norm_whistle_biased)

        wer_whisper = w_word_out.wer * 100.0
        wer_whistle = wh_word_out.wer * 100.0
        wer_whistle_b = whb_word_out.wer * 100.0

        cer_whisper = w_char_out.cer * 100.0
        cer_whistle = wh_char_out.cer * 100.0
        cer_whistle_b = whb_char_out.cer * 100.0

        # Raw WER
        raw_w_out = jiwer.process_words(ref_text, whisper_raw)
        raw_wh_out = jiwer.process_words(ref_text, whistle_raw)
        raw_wer_w = raw_w_out.wer * 100.0
        raw_wer_wh = raw_wh_out.wer * 100.0

        # Technical terms & Numbers
        tech_w_corr, tech_tot, tech_w_acc, tech_w_det = evaluate_technical_vocabulary(ref_text, whisper_raw, TECH_VOCAB[vid_key])
        tech_wh_corr, _, tech_wh_acc, tech_wh_det = evaluate_technical_vocabulary(ref_text, whistle_raw, TECH_VOCAB[vid_key])
        tech_whb_corr, _, tech_whb_acc, tech_whb_det = evaluate_technical_vocabulary(ref_text, whistle_biased_raw, TECH_VOCAB[vid_key])

        num_w_corr, num_tot, num_w_acc, _ = evaluate_numbers(ref_text, whisper_raw, NUMBERS[vid_key])
        num_wh_corr, _, num_wh_acc, _ = evaluate_numbers(ref_text, whistle_raw, NUMBERS[vid_key])
        num_whb_corr, _, num_whb_acc, _ = evaluate_numbers(ref_text, whistle_biased_raw, NUMBERS[vid_key])

        # Accumulate combined
        combined_stats["whisper"]["words_ref"] += num_ref_words
        combined_stats["whisper"]["s"] += w_word_out.substitutions
        combined_stats["whisper"]["d"] += w_word_out.deletions
        combined_stats["whisper"]["i"] += w_word_out.insertions
        combined_stats["whisper"]["c"] += w_word_out.hits
        combined_stats["whisper"]["chars_ref"] += num_ref_chars
        combined_stats["whisper"]["char_s"] += w_char_out.substitutions
        combined_stats["whisper"]["char_d"] += w_char_out.deletions
        combined_stats["whisper"]["char_i"] += w_char_out.insertions

        combined_stats["whistle"]["words_ref"] += num_ref_words
        combined_stats["whistle"]["s"] += wh_word_out.substitutions
        combined_stats["whistle"]["d"] += wh_word_out.deletions
        combined_stats["whistle"]["i"] += wh_word_out.insertions
        combined_stats["whistle"]["c"] += wh_word_out.hits
        combined_stats["whistle"]["chars_ref"] += num_ref_chars
        combined_stats["whistle"]["char_s"] += wh_char_out.substitutions
        combined_stats["whistle"]["char_d"] += wh_char_out.deletions
        combined_stats["whistle"]["char_i"] += wh_char_out.insertions

        combined_stats["whistle_biased"]["words_ref"] += num_ref_words
        combined_stats["whistle_biased"]["s"] += whb_word_out.substitutions
        combined_stats["whistle_biased"]["d"] += whb_word_out.deletions
        combined_stats["whistle_biased"]["i"] += whb_word_out.insertions
        combined_stats["whistle_biased"]["c"] += whb_word_out.hits
        combined_stats["whistle_biased"]["chars_ref"] += num_ref_chars
        combined_stats["whistle_biased"]["char_s"] += whb_char_out.substitutions
        combined_stats["whistle_biased"]["char_d"] += whb_char_out.deletions
        combined_stats["whistle_biased"]["char_i"] += whb_char_out.insertions

        # Fast word-by-word sequence alignment for side-by-side table
        ref_align_w, _, _, _, _ = align_words_sequence_matcher(ref_tokens, whisper_tokens)
        ref_align_wh, _, _, _, _ = align_words_sequence_matcher(ref_tokens, whistle_tokens)

        side_by_side = []
        for idx in range(len(ref_tokens)):
            ref_w = ref_tokens[idx]
            w_w, w_op = ref_align_w[idx]
            wh_w, wh_op = ref_align_wh[idx]

            if w_op == "C" and wh_op == "C":
                res = "Both correct"
            elif w_op == "C" and wh_op != "C":
                res = "Whisper correct"
            elif w_op != "C" and wh_op == "C":
                res = "Whistle correct"
            else:
                res = "Both incorrect"

            side_by_side.append({
                "position": idx + 1,
                "reference": ref_w,
                "whisper_base": w_w,
                "cactus_whistle": wh_w,
                "result": res
            })

        side_by_side_tables[vid_key] = side_by_side

        all_evaluations[vid_key] = {
            "num_reference_words": num_ref_words,
            "num_reference_chars": num_ref_chars,
            "normalized_metrics": {
                "whisper_base": {
                    "wer": round(wer_whisper, 2),
                    "cer": round(cer_whisper, 2),
                    "substitutions": w_word_out.substitutions,
                    "deletions": w_word_out.deletions,
                    "insertions": w_word_out.insertions,
                    "hits": w_word_out.hits
                },
                "cactus_whistle_baseline": {
                    "wer": round(wer_whistle, 2),
                    "cer": round(cer_whistle, 2),
                    "substitutions": wh_word_out.substitutions,
                    "deletions": wh_word_out.deletions,
                    "insertions": wh_word_out.insertions,
                    "hits": wh_word_out.hits
                },
                "cactus_whistle_biased": {
                    "wer": round(wer_whistle_b, 2),
                    "cer": round(cer_whistle_b, 2),
                    "substitutions": whb_word_out.substitutions,
                    "deletions": whb_word_out.deletions,
                    "insertions": whb_word_out.insertions,
                    "hits": whb_word_out.hits
                }
            },
            "raw_metrics": {
                "whisper_base_raw_wer": round(raw_wer_w, 2),
                "whistle_baseline_raw_wer": round(raw_wer_wh, 2)
            },
            "technical_vocabulary": {
                "terms_tested": tech_tot,
                "whisper_accuracy_pct": round(tech_w_acc, 2),
                "whistle_baseline_accuracy_pct": round(tech_wh_acc, 2),
                "whistle_biased_accuracy_pct": round(tech_whb_acc, 2),
                "details": {
                    "whisper": tech_w_det,
                    "whistle": tech_wh_det,
                    "whistle_biased": tech_whb_det
                }
            },
            "number_recognition": {
                "numbers_tested": num_tot,
                "whisper_accuracy_pct": round(num_w_acc, 2),
                "whistle_baseline_accuracy_pct": round(num_wh_acc, 2),
                "whistle_biased_accuracy_pct": round(num_whb_acc, 2)
            }
        }

        print(f"[{vid_key}] WER: Whisper {wer_whisper:.2f}% | Whistle {wer_whistle:.2f}% | Whistle Biased {wer_whistle_b:.2f}%")
        print(f"[{vid_key}] CER: Whisper {cer_whisper:.2f}% | Whistle {cer_whistle:.2f}%")
        print(f"[{vid_key}] Tech Vocab Acc: Whisper {tech_w_acc:.1f}% | Whistle {tech_wh_acc:.1f}% | Whistle Biased {tech_whb_acc:.1f}%")
        print(f"[{vid_key}] Numbers Acc: Whisper {num_w_acc:.1f}% | Whistle {num_wh_acc:.1f}% | Whistle Biased {num_whb_acc:.1f}%")

    # Combined corpus metrics
    corpus_results = {}
    for m in ["whisper", "whistle", "whistle_biased"]:
        st = combined_stats[m]
        tot_err = st["s"] + st["d"] + st["i"]
        tot_char_err = st["char_s"] + st["char_d"] + st["char_i"]
        corpus_wer = (tot_err / st["words_ref"]) * 100.0 if st["words_ref"] > 0 else 0.0
        corpus_cer = (tot_char_err / st["chars_ref"]) * 100.0 if st["chars_ref"] > 0 else 0.0
        corpus_results[m] = {
            "total_reference_words": st["words_ref"],
            "substitutions": st["s"],
            "deletions": st["d"],
            "insertions": st["i"],
            "hits": st["c"],
            "corpus_wer": round(corpus_wer, 2),
            "total_reference_chars": st["chars_ref"],
            "corpus_cer": round(corpus_cer, 2)
        }

    print("\n" + "="*70)
    print("COMBINED CORPUS-LEVEL ACCURACY RESULTS")
    print("="*70)
    print(f"Whisper Base:    WER {corpus_results['whisper']['corpus_wer']}% | CER {corpus_results['whisper']['corpus_cer']}% (Sub: {corpus_results['whisper']['substitutions']}, Del: {corpus_results['whisper']['deletions']}, Ins: {corpus_results['whisper']['insertions']})")
    print(f"Whistle Base:    WER {corpus_results['whistle']['corpus_wer']}% | CER {corpus_results['whistle']['corpus_cer']}% (Sub: {corpus_results['whistle']['substitutions']}, Del: {corpus_results['whistle']['deletions']}, Ins: {corpus_results['whistle']['insertions']})")
    print(f"Whistle Biased:  WER {corpus_results['whistle_biased']['corpus_wer']}% | CER {corpus_results['whistle_biased']['corpus_cer']}% (Sub: {corpus_results['whistle_biased']['substitutions']}, Del: {corpus_results['whistle_biased']['deletions']}, Ins: {corpus_results['whistle_biased']['insertions']})")

    # Load performance metrics
    with open(os.path.join(RESULTS_DIR, "performance_metrics.json"), "r", encoding="utf-8") as f:
        perf = json.load(f)

    # Word-level timestamp verification analysis
    timestamp_analysis = {}
    for vid_key in ["video1", "video2", "video3"]:
        with open(os.path.join(RESULTS_DIR, f"whisper_{vid_key}.json"), "r", encoding="utf-8") as f:
            w_json = json.load(f)
        with open(os.path.join(RESULTS_DIR, f"whistle_{vid_key}.json"), "r", encoding="utf-8") as f:
            wh_json = json.load(f)

        w_words = w_json.get("words", [])
        wh_words = wh_json.get("words", [])

        # Check monotonic timestamps and duration reasonableness
        w_monotonic = all(w_words[i]["start"] <= w_words[i+1]["start"] for i in range(len(w_words)-1)) if len(w_words) > 1 else True
        wh_monotonic = all(wh_words[i]["start"] <= wh_words[i+1]["start"] for i in range(len(wh_words)-1)) if len(wh_words) > 1 else True

        # Check average word confidence/probability
        w_avg_conf = np.mean([w["probability"] for w in w_words]) if w_words else 0.0
        wh_avg_conf = np.mean([w.get("probability", 1.0) for w in wh_words]) if wh_words else 0.0

        timestamp_analysis[vid_key] = {
            "whisper_words_count": len(w_words),
            "whisper_monotonic": w_monotonic,
            "whisper_avg_probability": round(float(w_avg_conf), 4),
            "whistle_words_count": len(wh_words),
            "whistle_monotonic": wh_monotonic,
            "whistle_avg_probability": round(float(wh_avg_conf), 4),
            "whistle_ttft_ms": wh_json.get("ttft_ms", 0.0),
            "whistle_decode_tps": wh_json.get("decode_tps", 0.0)
        }

    # Compile benchmark_results.json
    final_benchmark_results = {
        "benchmark_metadata": perf.get("benchmark_metadata", {}),
        "performance_metrics": {
            "whisper": perf.get("whisper", {}),
            "whistle": perf.get("whistle", {}),
            "total_experiment_duration_s": perf.get("total_experiment_duration_s", 0)
        },
        "accuracy_evaluations": all_evaluations,
        "corpus_level_summary": corpus_results,
        "timestamp_and_confidence_analysis": timestamp_analysis
    }

    out_json = os.path.join(BENCHMARK_DIR, "benchmark_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(final_benchmark_results, f, indent=2, ensure_ascii=False)
    print(f"\n[Saved] Compiled benchmark_results.json ({out_json})")

    # Save Side-by-Side Word Alignment Tables to files
    for vid_key, table in side_by_side_tables.items():
        table_path = os.path.join(RESULTS_DIR, f"alignment_{vid_key}.json")
        with open(table_path, "w", encoding="utf-8") as f:
            json.dump(table, f, indent=2, ensure_ascii=False)
            
        md_table_path = os.path.join(RESULTS_DIR, f"alignment_{vid_key}.md")
        with open(md_table_path, "w", encoding="utf-8") as f:
            f.write(f"# Word-by-Word Alignment Comparison: {vid_key}\n\n")
            f.write("| Position | Human Reference | Whisper Base | Cactus Whistle | Result |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- |\n")
            for row in table:
                f.write(f"| {row['position']} | {row['reference']} | {row['whisper_base']} | {row['cactus_whistle']} | {row['result']} |\n")
        print(f"[Saved] Alignment tables for {vid_key}: {len(table)} aligned positions")

    print("\nALL EVALUATION TASKS COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    main()
