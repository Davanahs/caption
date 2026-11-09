--
-- PostgreSQL database dump
--

-- Dumped from database version 15.8
-- Dumped by pg_dump version 15.8

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'WIN1252';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ab_experiments; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.ab_experiments (
    id character varying NOT NULL,
    clip_id character varying NOT NULL,
    youtube_short_id character varying(50) NOT NULL,
    variant_a_title character varying(500) NOT NULL,
    variant_b_title character varying(500) NOT NULL,
    active_variant character varying(50) NOT NULL,
    status character varying(50) NOT NULL,
    vsi_score_a double precision NOT NULL,
    vsi_score_b double precision NOT NULL,
    views_a integer NOT NULL,
    views_b integer NOT NULL,
    swapped_at character varying(100),
    winner_variant character varying(50),
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.ab_experiments OWNER TO clipforge_user;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO clipforge_user;

--
-- Name: channels; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.channels (
    id character varying NOT NULL,
    youtube_channel_id character varying(100) NOT NULL,
    channel_name character varying(200) NOT NULL,
    channel_url character varying(500) NOT NULL,
    thumbnail_url character varying(500),
    is_active boolean NOT NULL,
    auto_clip boolean NOT NULL,
    auto_publish boolean NOT NULL,
    last_checked_at timestamp with time zone,
    last_video_id character varying(50),
    clips_generated integer NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.channels OWNER TO clipforge_user;

--
-- Name: clips; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.clips (
    id character varying NOT NULL,
    video_id character varying NOT NULL,
    title character varying(500) NOT NULL,
    description text,
    start_time double precision NOT NULL,
    end_time double precision NOT NULL,
    duration double precision NOT NULL,
    score double precision DEFAULT '0'::double precision NOT NULL,
    output_path character varying(1000),
    thumbnail_path character varying(1000),
    transcript_segment text,
    publish_status character varying(50) DEFAULT 'draft'::character varying NOT NULL,
    youtube_short_id character varying(50),
    scheduled_at timestamp with time zone,
    published_at timestamp with time zone,
    privacy character varying(50) DEFAULT 'public'::character varying NOT NULL,
    made_for_kids boolean DEFAULT false NOT NULL,
    age_restricted boolean DEFAULT false NOT NULL,
    tags text,
    category character varying(100) DEFAULT '22'::character varying,
    license character varying(100) DEFAULT 'youtube'::character varying,
    created_at timestamp with time zone NOT NULL,
    pinned_comment character varying(200),
    metadata_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    analytics_views integer DEFAULT 0 NOT NULL,
    analytics_likes integer DEFAULT 0 NOT NULL,
    analytics_comments integer DEFAULT 0 NOT NULL,
    analytics_engagement_rate double precision DEFAULT '0'::double precision NOT NULL,
    analytics_view_score double precision DEFAULT '0'::double precision NOT NULL,
    analytics_last_checked character varying(50),
    analytics_check_count integer DEFAULT 0 NOT NULL,
    optimization_attempts integer DEFAULT 0 NOT NULL,
    last_optimized_at character varying(50)
);


ALTER TABLE public.clips OWNER TO clipforge_user;

--
-- Name: content_analysis; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.content_analysis (
    clip_id character varying NOT NULL,
    niche character varying(200) NOT NULL,
    topic character varying(500) NOT NULL,
    emotions character varying(500) NOT NULL,
    audience_type character varying(500) NOT NULL,
    searchable_keywords text NOT NULL,
    long_tail_keywords text NOT NULL,
    hashtag_candidates text NOT NULL,
    hook_type character varying(200) NOT NULL,
    pacing character varying(100) NOT NULL,
    sentiment_score double precision NOT NULL,
    analysis_json text NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.content_analysis OWNER TO clipforge_user;

--
-- Name: jobs; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.jobs (
    id character varying NOT NULL,
    video_id character varying,
    source_url character varying(500),
    source_title character varying(500),
    status character varying(50) NOT NULL,
    progress integer NOT NULL,
    current_step character varying(200),
    error_message text,
    celery_task_id character varying(200),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.jobs OWNER TO clipforge_user;

--
-- Name: metadata; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.metadata (
    id integer NOT NULL,
    video_id character varying NOT NULL,
    title character varying(200) NOT NULL,
    description text NOT NULL,
    tags character varying,
    hashtags character varying,
    pinned_comment character varying(150),
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.metadata OWNER TO clipforge_user;

--
-- Name: metadata_id_seq; Type: SEQUENCE; Schema: public; Owner: clipforge_user
--

CREATE SEQUENCE public.metadata_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.metadata_id_seq OWNER TO clipforge_user;

--
-- Name: metadata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: clipforge_user
--

ALTER SEQUENCE public.metadata_id_seq OWNED BY public.metadata.id;


--
-- Name: optimization_context; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.optimization_context (
    id character varying NOT NULL,
    clip_id character varying NOT NULL,
    previous_titles text NOT NULL,
    previous_descriptions text NOT NULL,
    previous_hashtags text NOT NULL,
    optimization_attempt integer NOT NULL,
    optimization_reason character varying(500) NOT NULL,
    previous_scores text NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.optimization_context OWNER TO clipforge_user;

--
-- Name: optimizations; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.optimizations (
    id integer NOT NULL,
    video_id character varying NOT NULL,
    attempt integer NOT NULL,
    new_title character varying(200),
    new_description text,
    new_tags character varying,
    new_hashtags character varying,
    view_score double precision,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.optimizations OWNER TO clipforge_user;

--
-- Name: optimizations_id_seq; Type: SEQUENCE; Schema: public; Owner: clipforge_user
--

CREATE SEQUENCE public.optimizations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.optimizations_id_seq OWNER TO clipforge_user;

--
-- Name: optimizations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: clipforge_user
--

ALTER SEQUENCE public.optimizations_id_seq OWNED BY public.optimizations.id;


--
-- Name: pipeline_metrics; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.pipeline_metrics (
    id character varying NOT NULL,
    clip_id character varying NOT NULL,
    phase_name character varying(100) NOT NULL,
    started_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone NOT NULL,
    duration_ms integer NOT NULL,
    success boolean NOT NULL,
    error_message text
);


ALTER TABLE public.pipeline_metrics OWNER TO clipforge_user;

--
-- Name: seo_analysis; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.seo_analysis (
    clip_id character varying NOT NULL,
    seo_score double precision NOT NULL,
    ctr_score double precision NOT NULL,
    discoverability_score double precision NOT NULL,
    missing_keywords text NOT NULL,
    recommended_hashtags text NOT NULL,
    weak_hashtags text NOT NULL,
    seo_json text NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.seo_analysis OWNER TO clipforge_user;

--
-- Name: video_analytics; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.video_analytics (
    id integer NOT NULL,
    video_id character varying NOT NULL,
    view_count integer NOT NULL,
    like_count integer NOT NULL,
    comment_count integer NOT NULL,
    fetched_at timestamp with time zone NOT NULL,
    view_score double precision
);


ALTER TABLE public.video_analytics OWNER TO clipforge_user;

--
-- Name: video_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: clipforge_user
--

CREATE SEQUENCE public.video_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.video_analytics_id_seq OWNER TO clipforge_user;

--
-- Name: video_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: clipforge_user
--

ALTER SEQUENCE public.video_analytics_id_seq OWNED BY public.video_analytics.id;


--
-- Name: video_tracking_queue; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.video_tracking_queue (
    id character varying NOT NULL,
    clip_id character varying NOT NULL,
    youtube_video_id character varying(50) NOT NULL,
    uploaded_at timestamp with time zone NOT NULL,
    next_check_at timestamp with time zone NOT NULL,
    optimization_attempts integer NOT NULL,
    last_score double precision,
    status character varying(50) NOT NULL
);


ALTER TABLE public.video_tracking_queue OWNER TO clipforge_user;

--
-- Name: videos; Type: TABLE; Schema: public; Owner: clipforge_user
--

CREATE TABLE public.videos (
    id character varying NOT NULL,
    title character varying(500) NOT NULL,
    youtube_url character varying(500),
    youtube_id character varying(50),
    local_path character varying(1000),
    duration double precision,
    thumbnail_url character varying(500),
    channel_id character varying(100),
    transcript text,
    auto_optimize boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.videos OWNER TO clipforge_user;

--
-- Name: metadata id; Type: DEFAULT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.metadata ALTER COLUMN id SET DEFAULT nextval('public.metadata_id_seq'::regclass);


--
-- Name: optimizations id; Type: DEFAULT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.optimizations ALTER COLUMN id SET DEFAULT nextval('public.optimizations_id_seq'::regclass);


--
-- Name: video_analytics id; Type: DEFAULT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.video_analytics ALTER COLUMN id SET DEFAULT nextval('public.video_analytics_id_seq'::regclass);


--
-- Data for Name: ab_experiments; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.ab_experiments (id, clip_id, youtube_short_id, variant_a_title, variant_b_title, active_variant, status, vsi_score_a, vsi_score_b, views_a, views_b, swapped_at, winner_variant, created_at) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.alembic_version (version_num) FROM stdin;
34087f10bf78
\.


--
-- Data for Name: channels; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.channels (id, youtube_channel_id, channel_name, channel_url, thumbnail_url, is_active, auto_clip, auto_publish, last_checked_at, last_video_id, clips_generated, created_at) FROM stdin;
\.


--
-- Data for Name: clips; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.clips (id, video_id, title, description, start_time, end_time, duration, score, output_path, thumbnail_path, transcript_segment, publish_status, youtube_short_id, scheduled_at, published_at, privacy, made_for_kids, age_restricted, tags, category, license, created_at, pinned_comment, metadata_status, analytics_views, analytics_likes, analytics_comments, analytics_engagement_rate, analytics_view_score, analytics_last_checked, analytics_check_count, optimization_attempts, last_optimized_at) FROM stdin;
1c5ba765-1cc3-423d-94ae-7b6aac950ed8	1c4bd9a1-6f38-4f82-8f14-63c23e624097	Untitled Clip	\N	0	15	15	5	D:\\automation video clips\\clipforge\\outputs\\1c4bd9a1-6f38-4f82-8f14-63c23e624097\\1c5ba765-1cc3-423d-94ae-7b6aac950ed8\\final.mp4	D:\\automation video clips\\clipforge\\outputs\\1c4bd9a1-6f38-4f82-8f14-63c23e624097\\1c5ba765-1cc3-423d-94ae-7b6aac950ed8\\thumbnail.jpg	.	draft	\N	\N	\N	public	f	f	\N	22	youtube	2026-08-25 14:35:52.318016+05:30	\N	pending	0	0	0	0	0	\N	0	0	\N
59a3feb3-f586-4bc2-80bc-4575210180e3	7874f6ac-ae07-4094-9fde-e4e222291576	Untitled Clip	\N	0	15	15	5	D:\\automation video clips\\clipforge\\outputs\\7874f6ac-ae07-4094-9fde-e4e222291576\\59a3feb3-f586-4bc2-80bc-4575210180e3\\final.mp4	D:\\automation video clips\\clipforge\\outputs\\7874f6ac-ae07-4094-9fde-e4e222291576\\59a3feb3-f586-4bc2-80bc-4575210180e3\\thumbnail.jpg	.	draft	\N	\N	\N	public	f	f	\N	22	youtube	2026-08-25 14:43:10.546241+05:30	\N	pending	0	0	0	0	0	\N	0	0	\N
ed93e4b8-5b39-477f-9186-8662b0507b0a	bc8a37e6-c0e8-4b48-bad1-867054b315d3	Untitled Clip	\N	0	15	15	5	D:\\automation video clips\\clipforge\\outputs\\bc8a37e6-c0e8-4b48-bad1-867054b315d3\\ed93e4b8-5b39-477f-9186-8662b0507b0a\\final.mp4	D:\\automation video clips\\clipforge\\outputs\\bc8a37e6-c0e8-4b48-bad1-867054b315d3\\ed93e4b8-5b39-477f-9186-8662b0507b0a\\thumbnail.jpg	.	draft	\N	\N	\N	public	f	f	\N	22	youtube	2026-08-25 14:48:43.391439+05:30	\N	pending	0	0	0	0	0	\N	0	0	\N
\.


--
-- Data for Name: content_analysis; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.content_analysis (clip_id, niche, topic, emotions, audience_type, searchable_keywords, long_tail_keywords, hashtag_candidates, hook_type, pacing, sentiment_score, analysis_json, created_at) FROM stdin;
b6710091-1f58-4333-bc30-1b36c7df6f44	Business & Entrepreneurship	Sales growth and marketing hacks	excitement,motivation,urgency	Entrepreneurs, business owners, and sales professionals	double sales,sales tips,business growth,marketing hacks,increase revenue	how to double your sales in 5 seconds,quick sales growth techniques,boost your business sales fast	#SalesGrowth,#BusinessTips,#MarketingStrategy,#EntrepreneurMindset,#DoubleYourSales	bold promise	fast	0.9	{"niche": "Business & Entrepreneurship", "topic": "Sales growth and marketing hacks", "secondary_topics": ["Sales optimization", "Business marketing strategies", "Entrepreneur tips"], "emotions": ["excitement", "motivation", "urgency"], "audience_type": "Entrepreneurs, business owners, and sales professionals", "content_style": "high-energy, promotional, educational", "pacing": "fast", "hook_type": "bold promise", "searchable_keywords": ["double sales", "sales tips", "business growth", "marketing hacks", "increase revenue"], "long_tail_keywords": ["how to double your sales in 5 seconds", "quick sales growth techniques", "boost your business sales fast"], "hashtag_candidates": ["#SalesGrowth", "#BusinessTips", "#MarketingStrategy", "#EntrepreneurMindset", "#DoubleYourSales"], "cta_style": "like and follow", "sentiment_score": 0.9}	2026-08-25 14:31:24.419853+05:30
1c5ba765-1cc3-423d-94ae-7b6aac950ed8	General	Untitled Clip	neutral	General audience	untitled,clip,intro,teaser,vlog	untitled clip analysis,short video intro,viral teaser	#untitled,#clip,#teaser,#viral,#shorts	curiosity	fast	0	{"niche": "General", "topic": "Untitled Clip", "secondary_topics": ["Introduction", "Teaser"], "emotions": ["neutral"], "audience_type": "General audience", "content_style": "high-energy", "pacing": "fast", "hook_type": "curiosity", "searchable_keywords": ["untitled", "clip", "intro", "teaser", "vlog"], "long_tail_keywords": ["untitled clip analysis", "short video intro", "viral teaser"], "hashtag_candidates": ["#untitled", "#clip", "#teaser", "#viral", "#shorts"], "cta_style": "like and follow", "sentiment_score": 0.0}	2026-08-25 14:35:52.311116+05:30
59a3feb3-f586-4bc2-80bc-4575210180e3	Entertainment	Untitled Clip	neutral,curious	General audience	untitled clip,short video,viral content,entertainment,general	untitled clip analysis,short video trends,general video content	#shorts,#viral,#entertainment,#clip,#untitled	curiosity	moderate	0.6	{"niche": "Entertainment", "topic": "Untitled Clip", "secondary_topics": ["General", "Miscellaneous"], "emotions": ["neutral", "curious"], "audience_type": "General audience", "content_style": "moderate", "pacing": "moderate", "hook_type": "curiosity", "searchable_keywords": ["untitled clip", "short video", "viral content", "entertainment", "general"], "long_tail_keywords": ["untitled clip analysis", "short video trends", "general video content"], "hashtag_candidates": ["#shorts", "#viral", "#entertainment", "#clip", "#untitled"], "cta_style": "like and follow", "sentiment_score": 0.6}	2026-08-25 14:43:10.538741+05:30
ed93e4b8-5b39-477f-9186-8662b0507b0a	Entertainment	Untitled Clip	Curiosity,Excitement	General audience	viral clip,trending video,shorts,entertainment,teaser	short viral video compilation,untitled clip teaser,high intensity short video	#viral,#shorts,#teaser,#entertainment,#clip	curiosity	fast	0.5	{"niche": "Entertainment", "topic": "Untitled Clip", "secondary_topics": ["Trending", "Viral Content"], "emotions": ["Curiosity", "Excitement"], "audience_type": "General audience", "content_style": "high-energy", "pacing": "fast", "hook_type": "curiosity", "searchable_keywords": ["viral clip", "trending video", "shorts", "entertainment", "teaser"], "long_tail_keywords": ["short viral video compilation", "untitled clip teaser", "high intensity short video"], "hashtag_candidates": ["#viral", "#shorts", "#teaser", "#entertainment", "#clip"], "cta_style": "like and follow", "sentiment_score": 0.5}	2026-08-25 14:48:43.386034+05:30
5c9bd131-fa2a-4918-8ec2-28abbe2d4b31	Animals	Elephants	curiosity,amazement,wonder	General audience	elephant trunk,elephant anatomy,why elephants have long trunks,elephant facts,animal adaptations	why elephants have long trunks explained,elephant trunk length evolution,fun facts about elephant trunks	#Elephants,#Trunk,#AnimalFacts,#Wildlife,#Nature	curiosity	fast	0.8	{"niche": "Animals", "topic": "Elephants", "secondary_topics": ["Elephant anatomy", "Animal adaptations", "Wildlife facts"], "emotions": ["curiosity", "amazement", "wonder"], "audience_type": "General audience", "content_style": "educational", "pacing": "fast", "hook_type": "curiosity", "searchable_keywords": ["elephant trunk", "elephant anatomy", "why elephants have long trunks", "elephant facts", "animal adaptations"], "long_tail_keywords": ["why elephants have long trunks explained", "elephant trunk length evolution", "fun facts about elephant trunks"], "hashtag_candidates": ["#Elephants", "#Trunk", "#AnimalFacts", "#Wildlife", "#Nature"], "cta_style": "like and follow", "sentiment_score": 0.8}	2026-08-25 16:33:51.753083+05:30
\.


--
-- Data for Name: jobs; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.jobs (id, video_id, source_url, source_title, status, progress, current_step, error_message, celery_task_id, created_at, updated_at) FROM stdin;
19a13d08-6229-4451-adf3-452edfe27505	1c4bd9a1-6f38-4f82-8f14-63c23e624097	e2e_verification_test.mp4	video	done	100	Done! Generated 1/1 clips.	\N	19a13d08-6229-4451-adf3-452edfe27505	2026-08-25 14:34:35.310233+05:30	2026-08-25 14:38:52.327683+05:30
df32d81e-96a5-4dc7-a07a-5458ec932b5a	b421c482-1cfe-4ea1-99b5-bf8426c11b6d	https://www.youtube.com/watch?v=jNQXAC9IVRw	Me at the zoo	done	100	Done! Generated 0/1 clips.	\N	df32d81e-96a5-4dc7-a07a-5458ec932b5a	2026-08-25 16:21:13.155912+05:30	2026-08-25 16:22:00.607965+05:30
d08b87e1-badc-4a74-bdd0-036e18b40010	a7a27815-f20e-4399-a9fd-aebac8384447	e2e_verification_test.mp4	video	done	100	Done! Generated 0/1 clips.	\N	d08b87e1-badc-4a74-bdd0-036e18b40010	2026-08-25 14:20:27.878237+05:30	2026-08-25 14:20:51.216113+05:30
9cb92eed-d879-43c8-be0b-691626290891	a9f4a5e6-0771-4aeb-8acf-badff598740d	https://www.youtube.com/watch?v=jNQXAC9IVRw	Me at the zoo	done	100	Done! Generated 0/1 clips.	\N	9cb92eed-d879-43c8-be0b-691626290891	2026-08-25 16:27:01.817714+05:30	2026-08-25 16:33:51.767144+05:30
b2b68469-f1c1-48b7-9a70-6a3e8bc20e83	\N	https://www.youtube.com/watch?v=M576Wl282A8	youtube.com/watch?v=M576Wl282A8	failed	0	Pipeline failed after 1 attempt(s)	yt-dlp info failed: ERROR: [youtube] M576Wl282A8: Video unavailable\n	b2b68469-f1c1-48b7-9a70-6a3e8bc20e83	2026-08-25 16:23:02.604178+05:30	2026-08-25 16:23:24.362929+05:30
c40e337a-16a0-48c4-85e2-882bbe0d10bd	7874f6ac-ae07-4094-9fde-e4e222291576	e2e_verification_test.mp4	video	done	100	Done! Generated 1/1 clips.	\N	c40e337a-16a0-48c4-85e2-882bbe0d10bd	2026-08-25 14:41:34.21258+05:30	2026-08-25 14:44:29.744856+05:30
dff25edc-709c-4acd-8f68-9d4b524b7b1e	4d568c6b-4d43-4cf2-911d-b8b69d44dbc2	e2e_verification_test.mp4	video	done	100	Done! Generated 0/1 clips.	\N	dff25edc-709c-4acd-8f68-9d4b524b7b1e	2026-08-25 14:21:05.109978+05:30	2026-08-25 14:21:29.366409+05:30
eb8ae642-4a3f-4ba6-a5f0-58629c409c26	bc8a37e6-c0e8-4b48-bad1-867054b315d3	e2e_verification_test.mp4	video	done	100	Done! Generated 1/1 clips.	\N	eb8ae642-4a3f-4ba6-a5f0-58629c409c26	2026-08-25 14:47:21.043021+05:30	2026-08-25 14:49:49.07642+05:30
074ccfbb-9392-4ba3-9ecc-f8cce7db00af	c87fe04f-11a4-4f55-b9b2-f47e590a893e	e2e_verification_test.mp4	video	done	100	Done! Generated 0/1 clips.	\N	074ccfbb-9392-4ba3-9ecc-f8cce7db00af	2026-08-25 14:25:57.501672+05:30	2026-08-25 14:31:24.445157+05:30
6fdf5681-17ae-4526-9c39-b2377d0ece6f	fc67e211-5605-47cf-a0ca-ee65c414835a	https://www.youtube.com/watch?v=jNQXAC9IVRw	Me at the zoo	done	100	Done! Generated 0/1 clips.	\N	6fdf5681-17ae-4526-9c39-b2377d0ece6f	2026-08-25 16:23:28.956545+05:30	2026-08-25 16:24:31.633621+05:30
698f9e92-5953-4562-a050-df18332d7a32	\N	https://www.youtube.com/watch?v=M576Wl282A8	youtube.com/watch?v=M576Wl282A8	failed	0	Pipeline failed after 1 attempt(s)	yt-dlp info failed: ERROR: [youtube] M576Wl282A8: This video is unavailable\n	698f9e92-5953-4562-a050-df18332d7a32	2026-08-25 16:14:41.732291+05:30	2026-08-25 16:15:03.275196+05:30
\.


--
-- Data for Name: metadata; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.metadata (id, video_id, title, description, tags, hashtags, pinned_comment, created_at) FROM stdin;
\.


--
-- Data for Name: optimization_context; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.optimization_context (id, clip_id, previous_titles, previous_descriptions, previous_hashtags, optimization_attempt, optimization_reason, previous_scores, created_at) FROM stdin;
\.


--
-- Data for Name: optimizations; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.optimizations (id, video_id, attempt, new_title, new_description, new_tags, new_hashtags, view_score, created_at) FROM stdin;
\.


--
-- Data for Name: pipeline_metrics; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.pipeline_metrics (id, clip_id, phase_name, started_at, completed_at, duration_ms, success, error_message) FROM stdin;
faa0545e-24c1-478a-ab25-1303a4b90176	a7a27815-f20e-4399-a9fd-aebac8384447	video download	2026-08-25 14:20:28.430108+05:30	2026-08-25 14:20:28.475801+05:30	45	t	\N
b9b1a3c3-533c-44eb-a354-ce95e722a3e6	a7a27815-f20e-4399-a9fd-aebac8384447	transcription	2026-08-25 14:20:28.582147+05:30	2026-08-25 14:20:31.973693+05:30	3391	t	\N
e8b9cb93-6d86-407c-8e81-db7b89b3c500	a7a27815-f20e-4399-a9fd-aebac8384447	scene detection	2026-08-25 14:20:28.582682+05:30	2026-08-25 14:20:31.975891+05:30	3393	t	\N
fb0d8e93-4fd4-40bc-978d-d1a08ee0c607	a7a27815-f20e-4399-a9fd-aebac8384447	clip scoring	2026-08-25 14:20:31.980528+05:30	2026-08-25 14:20:50.777228+05:30	18796	t	\N
863a7d88-0a6b-45d7-9598-dd2770329226	4d568c6b-4d43-4cf2-911d-b8b69d44dbc2	video download	2026-08-25 14:21:05.119387+05:30	2026-08-25 14:21:05.159218+05:30	39	t	\N
b1c9bdfd-bacc-428c-8374-4260d28c1e99	4d568c6b-4d43-4cf2-911d-b8b69d44dbc2	transcription	2026-08-25 14:21:05.267877+05:30	2026-08-25 14:21:08.430088+05:30	3162	t	\N
f2c10b03-56c9-4b39-b78d-286cbe0d68b8	4d568c6b-4d43-4cf2-911d-b8b69d44dbc2	scene detection	2026-08-25 14:21:05.267877+05:30	2026-08-25 14:21:08.431948+05:30	3164	t	\N
e98dee58-3865-4736-a14c-165a63ec8d6b	4d568c6b-4d43-4cf2-911d-b8b69d44dbc2	clip scoring	2026-08-25 14:21:08.436253+05:30	2026-08-25 14:21:28.991387+05:30	20555	t	\N
4c871a41-db55-4c19-bae8-886260f6ec01	c87fe04f-11a4-4f55-b9b2-f47e590a893e	video download	2026-08-25 14:25:57.978164+05:30	2026-08-25 14:25:58.032596+05:30	54	t	\N
5c04d947-16ef-4653-91cb-6ebc4f022aa0	c87fe04f-11a4-4f55-b9b2-f47e590a893e	transcription	2026-08-25 14:25:58.143336+05:30	2026-08-25 14:26:02.06723+05:30	3923	t	\N
42048f56-3578-48aa-a722-a3d49628aeb1	c87fe04f-11a4-4f55-b9b2-f47e590a893e	scene detection	2026-08-25 14:25:58.143856+05:30	2026-08-25 14:26:02.071282+05:30	3927	t	\N
7254c885-4b45-4772-93af-ffb8000ee52a	c87fe04f-11a4-4f55-b9b2-f47e590a893e	clip scoring	2026-08-25 14:26:02.079109+05:30	2026-08-25 14:26:37.332501+05:30	35253	t	\N
3f79d5a7-cd6c-48b6-8a0a-0efa8be2937c	b6710091-1f58-4333-bc30-1b36c7df6f44	ffmpeg processing	2026-08-25 14:26:37.341574+05:30	2026-08-25 14:30:50.826481+05:30	253484	t	\N
6ab1ed10-067b-42cd-9af6-b3fb78414a9b	1c4bd9a1-6f38-4f82-8f14-63c23e624097	video download	2026-08-25 14:34:35.552683+05:30	2026-08-25 14:34:35.602675+05:30	49	t	\N
a92d7dae-e26a-49f6-b5ff-58615419601f	1c4bd9a1-6f38-4f82-8f14-63c23e624097	transcription	2026-08-25 14:34:35.71816+05:30	2026-08-25 14:34:38.668119+05:30	2949	t	\N
e92b567f-93a2-4b7e-acd0-f7977c400a17	1c4bd9a1-6f38-4f82-8f14-63c23e624097	scene detection	2026-08-25 14:34:35.71816+05:30	2026-08-25 14:34:38.670385+05:30	2952	t	\N
5a6f2fe8-6799-4f72-8a5e-8e0ee9ad7bd9	1c4bd9a1-6f38-4f82-8f14-63c23e624097	clip scoring	2026-08-25 14:34:38.674678+05:30	2026-08-25 14:34:46.522843+05:30	7848	t	\N
fe441655-ba1d-4fb9-9401-04635996bc99	1c5ba765-1cc3-423d-94ae-7b6aac950ed8	ffmpeg processing	2026-08-25 14:34:46.530517+05:30	2026-08-25 14:35:30.366821+05:30	43836	t	\N
5802d0dd-946b-4e51-a424-9e7c598f4590	7874f6ac-ae07-4094-9fde-e4e222291576	video download	2026-08-25 14:41:34.733011+05:30	2026-08-25 14:41:34.794521+05:30	61	t	\N
40118bba-1466-41a5-9f67-863926548885	7874f6ac-ae07-4094-9fde-e4e222291576	transcription	2026-08-25 14:41:34.92415+05:30	2026-08-25 14:41:40.268779+05:30	5344	t	\N
fa2b49ac-2fec-45b4-88a5-94a7faf4e0be	7874f6ac-ae07-4094-9fde-e4e222291576	scene detection	2026-08-25 14:41:34.92415+05:30	2026-08-25 14:41:40.270797+05:30	5346	t	\N
5aa0ffeb-3191-421d-8278-125b7075bead	7874f6ac-ae07-4094-9fde-e4e222291576	clip scoring	2026-08-25 14:41:40.276087+05:30	2026-08-25 14:42:00.51589+05:30	20239	t	\N
ef1b5452-06c8-4076-9a6b-2163d5cb4dda	59a3feb3-f586-4bc2-80bc-4575210180e3	ffmpeg processing	2026-08-25 14:42:00.526861+05:30	2026-08-25 14:42:51.938972+05:30	51412	t	\N
42840de8-c222-4877-931a-ca08a47cb56e	bc8a37e6-c0e8-4b48-bad1-867054b315d3	video download	2026-08-25 14:47:21.444984+05:30	2026-08-25 14:47:21.486139+05:30	41	t	\N
35c3fb54-b17e-4619-942b-b33171ad8466	bc8a37e6-c0e8-4b48-bad1-867054b315d3	transcription	2026-08-25 14:47:21.594107+05:30	2026-08-25 14:47:22.722572+05:30	1128	t	\N
cf831980-6fdb-4f53-9556-f4c2d1c32ecd	bc8a37e6-c0e8-4b48-bad1-867054b315d3	scene detection	2026-08-25 14:47:21.594107+05:30	2026-08-25 14:47:22.724465+05:30	1130	t	\N
ba6e763e-3086-4da6-8265-332a5eeb3ff2	bc8a37e6-c0e8-4b48-bad1-867054b315d3	clip scoring	2026-08-25 14:47:22.726646+05:30	2026-08-25 14:47:42.825806+05:30	20099	t	\N
b00b4593-7196-447e-a58a-078e463083d2	ed93e4b8-5b39-477f-9186-8662b0507b0a	ffmpeg processing	2026-08-25 14:47:42.832679+05:30	2026-08-25 14:48:23.942933+05:30	41110	t	\N
ae679029-a530-4f0f-a503-59376371d38d	b421c482-1cfe-4ea1-99b5-bf8426c11b6d	video download	2026-08-25 16:21:13.167153+05:30	2026-08-25 16:21:24.160685+05:30	10993	t	\N
57b9af79-9bdf-4dd3-8311-e52a1c3fd9e9	b421c482-1cfe-4ea1-99b5-bf8426c11b6d	transcription	2026-08-25 16:21:24.292581+05:30	2026-08-25 16:21:25.667013+05:30	1374	t	\N
800938db-4c39-4945-9739-b36974bf1c9a	b421c482-1cfe-4ea1-99b5-bf8426c11b6d	scene detection	2026-08-25 16:21:24.292581+05:30	2026-08-25 16:21:25.669335+05:30	1376	t	\N
cf9d4d60-3371-43ba-afaf-1019a500ad97	b421c482-1cfe-4ea1-99b5-bf8426c11b6d	clip scoring	2026-08-25 16:21:25.673922+05:30	2026-08-25 16:21:47.969077+05:30	22295	t	\N
69a2f5db-a766-4d4f-9fd5-619332edd0c6	fc67e211-5605-47cf-a0ca-ee65c414835a	video download	2026-08-25 16:23:28.96416+05:30	2026-08-25 16:23:38.796273+05:30	9832	t	\N
38768c9b-5a73-4831-8635-b61343ca69a0	fc67e211-5605-47cf-a0ca-ee65c414835a	transcription	2026-08-25 16:23:38.858919+05:30	2026-08-25 16:23:40.063978+05:30	1205	t	\N
6e8ee0bb-414b-454b-8bf3-faed41f0145c	fc67e211-5605-47cf-a0ca-ee65c414835a	scene detection	2026-08-25 16:23:38.858919+05:30	2026-08-25 16:23:40.065177+05:30	1206	t	\N
36e755ef-f6e0-4348-9db6-0640360b9824	fc67e211-5605-47cf-a0ca-ee65c414835a	clip scoring	2026-08-25 16:23:40.06823+05:30	2026-08-25 16:24:19.637007+05:30	39568	t	\N
4f7ec8c0-b3aa-4298-bf5e-c13a6b0d76b0	a9f4a5e6-0771-4aeb-8acf-badff598740d	video download	2026-08-25 16:27:02.272179+05:30	2026-08-25 16:31:10.48926+05:30	248217	t	\N
72badec4-31b5-4794-abad-cd0c852f9a64	a9f4a5e6-0771-4aeb-8acf-badff598740d	transcription	2026-08-25 16:31:10.559815+05:30	2026-08-25 16:32:24.508335+05:30	73948	t	\N
aea56911-45d7-480d-ae4a-9a32986e072b	a9f4a5e6-0771-4aeb-8acf-badff598740d	scene detection	2026-08-25 16:31:10.559815+05:30	2026-08-25 16:32:24.50935+05:30	73949	t	\N
b754c8eb-aa40-4d52-b531-0a22d982d98e	a9f4a5e6-0771-4aeb-8acf-badff598740d	clip scoring	2026-08-25 16:32:24.510913+05:30	2026-08-25 16:33:16.165952+05:30	51655	t	\N
d8a24205-fcd0-4c33-930d-c5c791506c45	5c9bd131-fa2a-4918-8ec2-28abbe2d4b31	ffmpeg processing	2026-08-25 16:33:16.172221+05:30	2026-08-25 16:33:31.64675+05:30	15474	t	\N
\.


--
-- Data for Name: seo_analysis; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.seo_analysis (clip_id, seo_score, ctr_score, discoverability_score, missing_keywords, recommended_hashtags, weak_hashtags, seo_json, created_at) FROM stdin;
\.


--
-- Data for Name: video_analytics; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.video_analytics (id, video_id, view_count, like_count, comment_count, fetched_at, view_score) FROM stdin;
\.


--
-- Data for Name: video_tracking_queue; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.video_tracking_queue (id, clip_id, youtube_video_id, uploaded_at, next_check_at, optimization_attempts, last_score, status) FROM stdin;
\.


--
-- Data for Name: videos; Type: TABLE DATA; Schema: public; Owner: clipforge_user
--

COPY public.videos (id, title, youtube_url, youtube_id, local_path, duration, thumbnail_url, channel_id, transcript, auto_optimize, created_at) FROM stdin;
a7a27815-f20e-4399-a9fd-aebac8384447	video			D:\\automation video clips\\clipforge\\uploads\\37707f8c-2a38-4e9c-9419-10a2191902ca\\video.mp4	0	\N	\N	.	t	2026-08-25 14:20:28.434944+05:30
4d568c6b-4d43-4cf2-911d-b8b69d44dbc2	video			D:\\automation video clips\\clipforge\\uploads\\6cbd26f5-a64d-4857-a2fc-77e1e363cb7a\\video.mp4	0	\N	\N	.	t	2026-08-25 14:21:05.122542+05:30
c87fe04f-11a4-4f55-b9b2-f47e590a893e	video			D:\\automation video clips\\clipforge\\uploads\\9864d28f-7207-4cae-92ae-38a066eb0f88\\video.mp4	0	\N	\N	.	t	2026-08-25 14:25:57.986358+05:30
1c4bd9a1-6f38-4f82-8f14-63c23e624097	video			D:\\automation video clips\\clipforge\\uploads\\1ddcdcbc-9acf-4a31-ae92-538c317b56c8\\video.mp4	0	\N	\N	.	t	2026-08-25 14:34:35.559092+05:30
7874f6ac-ae07-4094-9fde-e4e222291576	video			D:\\automation video clips\\clipforge\\uploads\\5dd2b749-64d5-40ab-99de-917edf42a777\\video.mp4	0	\N	\N	.	t	2026-08-25 14:41:34.738474+05:30
bc8a37e6-c0e8-4b48-bad1-867054b315d3	video			D:\\automation video clips\\clipforge\\uploads\\133d767f-eecd-4040-8a4a-ef4fc007ce55\\video.mp4	0	\N	\N	.	t	2026-08-25 14:47:21.449111+05:30
b421c482-1cfe-4ea1-99b5-bf8426c11b6d	Me at the zoo	https://www.youtube.com/watch?v=jNQXAC9IVRw	jNQXAC9IVRw	D:\\automation video clips\\clipforge\\uploads\\b421c482-1cfe-4ea1-99b5-bf8426c11b6d\\video.mp4	19	\N	\N	Alright, so here we are, one of the elephants. The cool thing about these guys is that they have really, really, really long fronts. And that's cool. And that's pretty much all there is to say.	t	2026-08-25 16:21:24.104678+05:30
fc67e211-5605-47cf-a0ca-ee65c414835a	Me at the zoo	https://www.youtube.com/watch?v=jNQXAC9IVRw	jNQXAC9IVRw	D:\\automation video clips\\clipforge\\uploads\\fc67e211-5605-47cf-a0ca-ee65c414835a\\video.mp4	19	\N	\N	Alright, so here we are, one of the elephants. The cool thing about these guys is that they have really, really, really long fronts. And that's cool. And that's pretty much all there is to say.	t	2026-08-25 16:23:38.757646+05:30
a9f4a5e6-0771-4aeb-8acf-badff598740d	Me at the zoo	https://www.youtube.com/watch?v=jNQXAC9IVRw	jNQXAC9IVRw	D:\\automation video clips\\clipforge\\uploads\\a9f4a5e6-0771-4aeb-8acf-badff598740d\\video.mp4	19	\N	\N	Alright, so here we are, one of the elephants. The cool thing about these guys is that they have really, really, really long fronts. And that's cool. And that's pretty much all there is to say.	t	2026-08-25 16:31:10.446686+05:30
\.


--
-- Name: metadata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: clipforge_user
--

SELECT pg_catalog.setval('public.metadata_id_seq', 1, false);


--
-- Name: optimizations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: clipforge_user
--

SELECT pg_catalog.setval('public.optimizations_id_seq', 1, false);


--
-- Name: video_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: clipforge_user
--

SELECT pg_catalog.setval('public.video_analytics_id_seq', 1, false);


--
-- Name: ab_experiments ab_experiments_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.ab_experiments
    ADD CONSTRAINT ab_experiments_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: channels channels_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_pkey PRIMARY KEY (id);


--
-- Name: channels channels_youtube_channel_id_key; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_youtube_channel_id_key UNIQUE (youtube_channel_id);


--
-- Name: clips clips_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.clips
    ADD CONSTRAINT clips_pkey PRIMARY KEY (id);


--
-- Name: content_analysis content_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.content_analysis
    ADD CONSTRAINT content_analysis_pkey PRIMARY KEY (clip_id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: metadata metadata_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.metadata
    ADD CONSTRAINT metadata_pkey PRIMARY KEY (id);


--
-- Name: optimization_context optimization_context_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.optimization_context
    ADD CONSTRAINT optimization_context_pkey PRIMARY KEY (id);


--
-- Name: optimizations optimizations_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.optimizations
    ADD CONSTRAINT optimizations_pkey PRIMARY KEY (id);


--
-- Name: pipeline_metrics pipeline_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.pipeline_metrics
    ADD CONSTRAINT pipeline_metrics_pkey PRIMARY KEY (id);


--
-- Name: seo_analysis seo_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.seo_analysis
    ADD CONSTRAINT seo_analysis_pkey PRIMARY KEY (clip_id);


--
-- Name: video_analytics video_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.video_analytics
    ADD CONSTRAINT video_analytics_pkey PRIMARY KEY (id);


--
-- Name: video_tracking_queue video_tracking_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.video_tracking_queue
    ADD CONSTRAINT video_tracking_queue_pkey PRIMARY KEY (id);


--
-- Name: videos videos_pkey; Type: CONSTRAINT; Schema: public; Owner: clipforge_user
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);


--
-- Name: ix_metadata_id; Type: INDEX; Schema: public; Owner: clipforge_user
--

CREATE INDEX ix_metadata_id ON public.metadata USING btree (id);


--
-- Name: ix_optimizations_id; Type: INDEX; Schema: public; Owner: clipforge_user
--

CREATE INDEX ix_optimizations_id ON public.optimizations USING btree (id);


--
-- Name: ix_video_analytics_id; Type: INDEX; Schema: public; Owner: clipforge_user
--

CREATE INDEX ix_video_analytics_id ON public.video_analytics USING btree (id);


--
-- Name: ix_video_analytics_video_id; Type: INDEX; Schema: public; Owner: clipforge_user
--

CREATE INDEX ix_video_analytics_video_id ON public.video_analytics USING btree (video_id);


--
-- PostgreSQL database dump complete
--

