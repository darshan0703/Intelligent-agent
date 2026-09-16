--
-- PostgreSQL database dump
--

\restrict GGglollqtqpG92fltMQN4PTh1k0gu4zyvaqQcfybmDcWFazquct6XrZ8oZwqinF

-- Dumped from database version 14.21 (Homebrew)
-- Dumped by pg_dump version 14.21 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: branches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.branches (
    id integer NOT NULL,
    name character varying NOT NULL,
    brand_id integer NOT NULL
);


--
-- Name: branches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.branches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: branches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.branches_id_seq OWNED BY public.branches.id;


--
-- Name: brands; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brands (
    id integer NOT NULL,
    name character varying NOT NULL
);


--
-- Name: brands_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.brands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: brands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.brands_id_seq OWNED BY public.brands.id;


--
-- Name: cross_sell; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_sell (
    id integer NOT NULL,
    source_item_id integer NOT NULL,
    recommended_item_id integer NOT NULL,
    priority integer
);


--
-- Name: cross_sell_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cross_sell_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cross_sell_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cross_sell_id_seq OWNED BY public.cross_sell.id;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    branch_id integer NOT NULL,
    item_id integer NOT NULL,
    stock integer NOT NULL,
    expiry_date date
);


--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: meal_defaults; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meal_defaults (
    id integer NOT NULL,
    meal_size character varying(20) NOT NULL,
    default_side_id integer NOT NULL,
    default_drink_id integer NOT NULL
);


--
-- Name: meal_defaults_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.meal_defaults_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meal_defaults_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meal_defaults_id_seq OWNED BY public.meal_defaults.id;


--
-- Name: meal_upgrade_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meal_upgrade_rules (
    id integer NOT NULL,
    item_id integer NOT NULL,
    meal_size character varying(20) NOT NULL,
    extra_price numeric DEFAULT 0 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL
);


--
-- Name: meal_upgrade_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.meal_upgrade_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: meal_upgrade_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.meal_upgrade_rules_id_seq OWNED BY public.meal_upgrade_rules.id;


--
-- Name: menu_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.menu_items (
    id integer NOT NULL,
    name character varying NOT NULL,
    short_description character varying,
    long_description character varying,
    price numeric NOT NULL,
    image character varying,
    category character varying NOT NULL,
    section character varying,
    food_type character varying,
    display_order integer,
    is_meal_available boolean,
    is_available boolean,
    section_order integer,
    serving_type character varying,
    meal_role character varying,
    meal_size character varying(20),
    is_meal_only boolean DEFAULT false NOT NULL,
    meal_image character varying
);


--
-- Name: menu_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.menu_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: menu_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.menu_items_id_seq OWNED BY public.menu_items.id;


--
-- Name: branches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branches ALTER COLUMN id SET DEFAULT nextval('public.branches_id_seq'::regclass);


--
-- Name: brands id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brands ALTER COLUMN id SET DEFAULT nextval('public.brands_id_seq'::regclass);


--
-- Name: cross_sell id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_sell ALTER COLUMN id SET DEFAULT nextval('public.cross_sell_id_seq'::regclass);


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: meal_defaults id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_defaults ALTER COLUMN id SET DEFAULT nextval('public.meal_defaults_id_seq'::regclass);


--
-- Name: meal_upgrade_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_upgrade_rules ALTER COLUMN id SET DEFAULT nextval('public.meal_upgrade_rules_id_seq'::regclass);


--
-- Name: menu_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items ALTER COLUMN id SET DEFAULT nextval('public.menu_items_id_seq'::regclass);


--
-- Data for Name: branches; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.branches (id, name, brand_id) FROM stdin;
1	Bangalore Branch	1
\.


--
-- Data for Name: brands; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.brands (id, name) FROM stdin;
1	Demo Burger Brand
2	Burger King
\.


--
-- Data for Name: cross_sell; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cross_sell (id, source_item_id, recommended_item_id, priority) FROM stdin;
\.


--
-- Data for Name: inventory; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.inventory (id, branch_id, item_id, stock, expiry_date) FROM stdin;
5	1	5	20	2026-12-31
6	1	6	20	2026-12-31
7	1	7	20	2026-12-31
10	1	10	20	2026-12-31
12	1	12	20	2026-12-31
13	1	13	20	2026-12-31
14	1	14	20	2026-12-31
15	1	15	20	2026-12-31
16	1	16	20	2026-12-31
17	1	17	20	2026-12-31
18	1	18	20	2026-12-31
19	1	19	20	2026-12-31
20	1	20	20	2026-12-31
21	1	21	20	2026-12-31
22	1	22	20	2026-12-31
24	1	24	20	2026-12-31
27	1	27	20	2026-12-31
28	1	28	20	2026-12-31
29	1	29	20	2026-12-31
30	1	30	20	2026-12-31
31	1	31	20	2026-12-31
32	1	32	20	2026-12-31
33	1	33	20	2026-12-31
34	1	34	20	2026-12-31
35	1	35	20	2026-12-31
36	1	36	20	2026-12-31
37	1	37	20	2026-12-31
38	1	38	20	2026-12-31
43	1	43	20	2026-12-31
45	1	45	20	2026-12-31
47	1	47	20	2026-12-31
48	1	48	20	2026-12-31
50	1	50	20	2026-12-31
51	1	51	20	2026-12-31
52	1	52	20	2026-12-31
53	1	53	20	2026-12-31
54	1	54	20	2026-12-31
55	1	55	20	2026-12-31
56	1	56	20	2026-12-31
57	1	57	20	2026-12-31
58	1	58	20	2026-12-31
59	1	59	20	2026-12-31
60	1	60	20	2026-12-31
61	1	61	20	2026-12-31
62	1	62	20	2026-12-31
63	1	63	20	2026-12-31
64	1	64	20	2026-12-31
67	1	67	20	2026-12-31
68	1	68	20	2026-12-31
70	1	70	20	2026-12-31
71	1	71	20	2026-12-31
72	1	72	20	2026-12-31
73	1	73	20	2026-12-31
74	1	74	20	2026-12-31
75	1	75	20	2026-12-31
76	1	76	20	2026-12-31
77	1	77	20	2026-12-31
78	1	78	20	2026-12-31
79	1	79	20	2026-12-31
80	1	80	20	2026-12-31
81	1	81	20	2026-12-31
82	1	82	20	2026-12-31
83	1	83	20	2026-12-31
84	1	84	20	2026-12-31
85	1	46	100	2026-08-31
86	1	39	100	2026-08-28
87	1	42	100	2026-08-28
88	1	85	50	2026-08-29
4	1	4	19	2026-12-31
2	1	2	19	2026-12-31
26	1	26	19	2026-12-31
1	1	1	18	2026-12-31
25	1	25	19	2026-12-31
3	1	3	19	2026-12-31
11	1	11	19	2026-12-31
66	1	66	18	2026-12-31
41	1	41	19	2026-12-31
23	1	23	19	2026-12-31
8	1	8	19	2026-12-31
69	1	69	19	2026-12-31
49	1	49	19	2026-12-31
9	1	9	19	2026-12-31
65	1	65	16	2026-12-31
40	1	40	16	2026-12-31
\.


--
-- Data for Name: meal_defaults; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.meal_defaults (id, meal_size, default_side_id, default_drink_id) FROM stdin;
1	medium	65	40
2	large	66	40
\.


--
-- Data for Name: meal_upgrade_rules; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.meal_upgrade_rules (id, item_id, meal_size, extra_price, is_enabled) FROM stdin;
107	65	medium	0	t
108	66	large	0	t
109	67	medium	30	t
110	68	large	40	t
111	69	medium	40	t
112	69	large	40	t
113	70	medium	0	t
114	70	large	0	t
115	74	medium	45	t
116	74	large	45	t
117	85	medium	59	t
118	85	large	59	t
119	17	medium	0	t
120	17	large	0	t
121	39	medium	15	t
122	42	large	15	t
123	46	medium	15	t
124	47	large	15	t
125	48	medium	0	t
126	48	large	0	t
127	49	medium	0	t
128	49	large	0	t
129	24	medium	79	t
130	24	large	79	t
131	25	medium	79	t
132	25	large	79	t
133	26	medium	79	t
134	26	large	79	t
135	31	medium	79	t
136	31	large	79	t
137	50	medium	79	t
138	50	large	79	t
139	51	medium	79	t
140	51	large	79	t
141	52	medium	79	t
142	52	large	79	t
143	53	medium	99	t
144	53	large	99	t
145	27	medium	59	t
146	27	large	59	t
147	28	medium	59	f
148	28	large	59	f
149	29	medium	59	t
150	29	large	59	t
151	30	medium	59	f
152	30	large	59	f
153	32	medium	59	t
154	32	large	59	t
155	33	medium	59	f
156	33	large	59	f
157	34	medium	59	t
158	34	large	59	t
159	35	medium	59	f
160	35	large	59	f
161	36	medium	59	t
162	36	large	59	t
163	37	medium	59	f
164	37	large	59	f
165	38	medium	59	t
166	38	large	59	t
167	40	medium	0	t
168	40	large	0	t
169	41	medium	0	t
170	41	large	0	t
171	43	medium	0	t
172	43	large	0	t
173	45	medium	0	t
174	45	large	0	t
\.


--
-- Data for Name: menu_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.menu_items (id, name, short_description, long_description, price, image, category, section, food_type, display_order, is_meal_available, is_available, section_order, serving_type, meal_role, meal_size, is_meal_only, meal_image) FROM stdin;
13	BK Veggie	Mix veg patty, lettuce, tomato & mayo.	New Premium Black & White Sesame Bun with Mix Veg Patty, Lettuce, Tomato(Seasonal) & Our Signature Mayo.	139	src/assets/images/Burgers/BK Veggie.png	burger	Crazy Deals	veg	1	t	t	4	\N	main	\N	f	src/assets/images/Meals/BK Veggie Burger meal.png
12	Paneer Royale	Paneer patty with signature sauces in brioche buns.	60 gm Paneer Patty, Sauces In premium Brioche Buns.Qty: 253 gms | Kcal: 600 | Carbs: 58 gms| Sugar: 10 gms| Fat: 33 gms| Saturated fat: 14 gms| Protein: 20.8 gms| Sodium: 1314 mg	209	src/assets/images/Burgers/Paneer Royale.png	burger	Premium Burgers	veg	1	t	t	3	\N	main	\N	f	src/assets/images/Meals/Paneer Whopper Deluxe meal.png
11	Cheese Whopper	Cheese lava patty with fresh veggies & sauces.	Reg. size bun with 7 layers of taste: Molten Cheese Lava patty, fresh onion, crispy lettuce, juicy tomatoes (seasonal), tangy gherkins, creamy & smoky sauces.Qty: 201 gms | Kcal: 516 | Carbs: 47 gms| Sugar: 8 gms| Fat: 30 gms| Saturated fat: 13 gms| Protein: 15.3 gms| Sodium: 1530 mg	179	src/assets/images/Burgers/Cheese Whopper.png	burger	Whoppers	veg	5	t	t	2	\N	main	\N	f	src/assets/images/Meals/Cheese Whopper Deluxe meal.png
10	Paneer Whopper	Crunchy paneer patty with fresh veggies.	Reg. size bun with 7 layers of taste: Crunchy Soft Paneer patty, fresh onion, crispy lettuce, juicy tomatoes (seasonal), tangy gherkins, creamy & smoky sauces.Qty: 197 gms | Kcal: 472 | Carbs: 43 gms| Sugar: 8 gms| Fat: 27 gms| Saturated fat: 13 gms| Protein: 16.4 gms| Sodium: 1042 mg	169	src/assets/images/Burgers/Paneer Whopper.png	burger	Whoppers	veg	4	t	t	2	\N	main	\N	f	src/assets/images/Meals/Paneer Whopper Deluxe meal.png
9	Grill Chicken Whopper	Flame-grilled chicken, lettuce & smoky sauces.	Regular Size premium glaze bun with 7 layers of taste: Flame-Grilled Chicken patty, fresh onion, crispy lettuce, juicy tomatoes (seasonal) tangy gherkins, creamy & smoky sauces.Qty: 179 gms | Kcal: 327 | Carbs: 35 gms| Sugar: 1 gms| Fat: 14 gms| Saturated fat: 3 gms| Protein: 14.3 gms| Sodium: 952 mg	169	src/assets/images/Burgers/Grill Chicken Whopper.png	burger	Whoppers	non veg	3	t	t	2	\N	main	\N	f	src/assets/images/Meals/Grill Chicken Whopper Deluxe meal.png
8	Chicken Whopper	Flame-grilled chicken with fresh veggies & sauces.	XL Size Original Whopper Chicken in premium glaze bun. 7 layers of taste: Flame Grill Chicken patty, fresh onion, crispy lettuce, juicy tomatoes (seasonal), tangy gherkins, creamy & smoky sauces.Qty: 280 Gms| Kcal: 667.2 | Carbs 59.1 Gms| Sugar: 8.7 Gms| Fat: 36.3 Gms| Saturated fat: 8.1 Gms| Protein: 26.2 Gms| Sodium: 1018.7 Mg Contains: Gluten, Soybean, Milk, Sesame seeds.	209	src/assets/images/Burgers/Chicken Whopper.png	burger	Whoppers	non veg	2	t	t	2	\N	main	\N	f	src/assets/images/Meals/Chicken Whopper Deluxe meal.png
7	Veg Whopper	XL veg whopper with fresh veggies & smoky sauces.	XL Size Original Whopper Veg in premium glaze bun. 7 layers of taste: Extra Crunchy Veg patty, fresh onion, crispy lettuce, juicy tomatoes (seasonal), tangy gherkins, creamy & smoky sauces.Qty: 303 gms | Kcal: 367 | Carbs: 48 gms| Sugar: 11 gms| Fat: 13 gms| Saturated fat: 3 gms| Protein: 16 gms| Sodium: 761 mg	189	src/assets/images/Burgers/Veg Whopper.png	burger	Whoppers	veg	1	t	t	2	\N	main	\N	f	src/assets/images/Meals/Veg Whopper Deluxe meal.png
6	Crispy Chicken Double Patty	Double crispy chicken patties for extra crunch.	Double up the crispy chicken patty burger.Qty: 183 gms | Kcal: 429 | Carbs: 41 gms| Sugar: 6 gms| Fat: 21 gms| Saturated fat: 8 gms| Protein: 20.4 gms| Sodium: 638 mg	119	src/assets/images/Burgers/Crispy Chicken Double Patty.png	burger	Value Burgers	non veg	6	t	t	1	\N	main	\N	f	src/assets/images/Meals/Crispy Chicken Double Patty meal.png
22	Peri Peri Cheese	Spicy cheese burger with fresh vegetables.	Molten Cheese Lava patty dunked in hot & spicy Peri Peri glaze with herby mayo in premium brioche buns for authentic Peri Peri flavours.	239	src/assets/images/Burgers/Peri Peri Cheese.png	burger	Peri Peri	veg	4	t	t	6	\N	main	\N	f	src/assets/images/Meals/Peri Peri Cheese Burger meal.png
28	Espresso (Double Shot)	Bold double shot of rich espresso.	Rich Shot of our signature BK Café Coffee without milk.	109	src/assets/images/Drinks/Espresso (Double Shot).png	drink	BK Café	veg	5	f	t	1	hot	\N	\N	f	\N
30	Americano (Regular)	Rich espresso with hot water.	Our signature BK Café Coffee with Sweet Caramel Flavour.	189	src/assets/images/Drinks/Americano (Regular).png	drink	BK Café	veg	7	f	t	1	hot	\N	\N	f	\N
33	Cafe Latte (Regular)	Smooth espresso with steamed milk.	Our signature BK Café Coffee with steamed milk.	189	src/assets/images/Drinks/Cafe Latte (Regular).png	drink	BK Café	veg	10	f	t	1	hot	\N	\N	f	\N
35	Cappuccino (Regular)	Regular cappuccino with milk foam.	Espresso with steamed milk & milk froth.	179	src/assets/images/Drinks/Cappuccino (Regular).png	drink	BK Café	veg	12	f	t	1	hot	\N	\N	f	\N
37	Mocha Cappuccino (Regular)	Regular mocha cappuccino with chocolate flavor.	Rich Chocolate Flavoured Coffee.	219	src/assets/images/Drinks/Mocha Cappuccino (Regular).png	drink	BK Café	veg	14	f	t	1	hot	\N	\N	f	\N
21	Peri Peri Paneer	Spicy peri peri paneer burger with fresh vegetables.	Crispy paneer patty dunked in hot & spicy Peri Peri glaze with herby mayo in premium brioche buns for authentic Peri Peri flavours	219	src/assets/images/Burgers/Peri Peri Paneer.png	burger	Peri Peri	veg	3	t	t	6	\N	main	\N	f	src/assets/images/Meals/Peri Peri Paneer Burger meal.png
80	Chicken Wings - Fried (15 Pcs)	Crunchy fried chicken pieces.	Juicy chicken wings cooked to perfection.	519	src/assets/images/sides/Chicken Wings - Fried (15 Pcs).png	side	Nuggets	non veg	11	f	t	2	\N	\N	\N	f	\N
40	Large Coca cola	Large classic chilled Coca-Cola soft drink.	Coca Cola.	131	src/assets/images/Drinks/Coca Cola.png	drink	Cold Drinks	veg	2	f	t	2	cold	drink		f	\N
24	Classic Cold Coffee	Refreshing classic cold coffee with milk.	Our signature BK Café Coffee ice blended with milk & cream.	189	src/assets/images/Drinks/Classic Cold Coffee.png	drink	BK Café	veg	1	f	t	1	cold	drink	\N	f	\N
45	Large Thums Up	Bold and fizzy cola drink.	Thums Up.	111	src/assets/images/Drinks/Large Thums Up.png	drink	Cold Drinks	veg	7	f	t	2	cold	drink		f	\N
43	Large Fanta	Refreshing orange flavored soft drink.	Fanta.	111	src/assets/images/Drinks/Fanta.png	drink	Cold Drinks	veg	5	f	t	2	cold	drink		f	\N
41	Large Sprite	Refreshing lemon-lime soft drink.	Sprite.	111	src/assets/images/Drinks/Sprite.png	drink	Cold Drinks	veg	3	f	t	2	cold	drink		f	\N
25	Iced Latte	Chilled espresso blended with creamy milk.	100% Arabica Espresso poured over milk and ice.	199	src/assets/images/Drinks/Iced Latte.png	drink	BK Café	veg	2	f	t	1	cold	drink	\N	f	\N
26	Mocha Frappe	Chocolate coffee frappe topped with vanilla soft serve.	Chocolate flavoured Cold Coffee topped with Vanilla Softie.Qty: 355 gms| Kcal: 293 | Carbs: 52.2 gms| Sugar: 45.7 gms| Fat: 7.5 gms| Saturated fat: 5.5 gms| Protein: 4.3 gms|	249	src/assets/images/Drinks/Mocha Frappe.png	drink	BK Café	veg	3	f	t	1	cold	drink	\N	f	\N
31	Iced Americano	Refreshing iced Americano coffee.	Our signature Arabica espresso with ice.	159	src/assets/images/Drinks/Iced Americano.png	drink	BK Café	veg	8	f	t	1	cold	drink	\N	f	\N
27	Espresso (Single Shot)	Bold single shot of rich espresso.	Rich Shot of our signature BK Café Coffee without milk.	109	src/assets/images/Drinks/Espresso (Single Shot).png	drink	BK Café	veg	4	f	t	1	hot	drink	\N	f	\N
29	Americano (Small)	Small serving of rich Americano.	Our signature BK Café Coffee with Sweet Caramel Flavour.	189	src/assets/images/Drinks/Americano (Small).png	drink	BK Café	veg	6	f	t	1	hot	drink	\N	f	\N
32	Cafe Latte (Small)	Small creamy latte with steamed milk.	Our signature BK Café Coffee with steamed milk.	159	src/assets/images/Drinks/Cafe Latte (Small).png	drink	BK Café	veg	9	f	t	1	hot	drink	\N	f	\N
34	Cappuccino (Small)	Creamy cappuccino with milk foam.	Our signature BK Café Coffee with steamed milk & milk froth.	149	src/assets/images/Drinks/Cappuccino (Small).png	drink	BK Café	veg	11	f	t	1	hot	drink	\N	f	\N
36	Mocha Cappuccino (Small)	Chocolate cappuccino with rich mocha flavor.	Our signature BK Café Coffee with Rich Chocolate Flavour.	195	src/assets/images/Drinks/Mocha Cappuccino (Small).png	drink	BK Café	veg	13	f	t	1	hot	drink	\N	f	\N
38	Hot Chocolate	Creamy hot chocolate made with rich cocoa.	The chocolate which you can drink. Rich Creamy Chocolate with steamed milk.	179	src/assets/images/Drinks/Hot Chocolate.png	drink	BK Café	veg	15	f	t	1	hot	drink	\N	f	\N
47	Masala Fizz (Medium)	Sparkling masala flavored fizzy drink.	A fizzy twist to your favourite Coke — now with full on Masala flavour.Qty: 450ml| Kcal: 88.34 | Carbs: 22.08 gms| Sugar: 22.07 gms| Fat: 0.0 gms| Saturated fat: 0 gms| Protein: 0.0 gms| Sodium: 734.00 mg	129	src/assets/images/Drinks/Masala Fizz.png	drink	Cold Drinks	veg	8	f	t	2	cold	drink	\N	f	\N
54	Vanilla Softie	Creamy vanilla soft serve in a crispy cone.	Ice cream with cone. Anytime happiness.	33	src/assets/images/Dessert/Vanilla Softie.png	dessert	Soft Serve	veg	1	f	t	1	\N	\N	\N	f	\N
55	Choco Dip Softie	Vanilla soft serve coated with rich chocolate.	Ice cream dipped in chocolate.	50	src/assets/images/Dessert/Choco Dip Softie.png	dessert	Soft Serve	veg	2	f	t	1	\N	\N	\N	f	\N
56	Vanilla Softie Waffle Cone	Creamy vanilla soft serve in a crunchy waffle cone.	Vanilla Softie with crunchy Waffle Cone. Delicious crunchy happinessQty: 80 gms| Kcal: 77 | Carbs: 10.7 gms| Sugar: 9.3 gms| Fat: 3.3 gms| Saturated fat: 1.8 gms| Protein: 1.8 gms|	38	src/assets/images/Dessert/Vanilla Softie Waffle Cone.png	dessert	Waffle Cones	veg	1	f	t	2	\N	\N	\N	f	\N
57	Choco Dip Softie Waffle Cone	Chocolate-coated soft serve in a crunchy waffle cone.	Choco Dip Softie with crunchy Waffle Cone. Delicious crunchy happiness.Qty: 95 gms| Kcal: 172 | Carbs: 17.1 gms| Sugar: 15.1 gms| Fat: 10.5 gms| Saturated fat: 7.4 gms| Protein: 2.4 gms|	55	src/assets/images/Dessert/Choco Dip Softie Waffle Cone.png	dessert	Waffle Cones	veg	2	f	t	2	\N	\N	\N	f	\N
58	Mango Sundae	Creamy vanilla sundae topped with sweet mango sauce.	Ice cream served with mango puree.	45	src/assets/images/Dessert/Mango sundae.png	dessert	Sundaes	veg	1	f	t	3	\N	\N	\N	f	\N
59	Black Currant Sundae	Creamy vanilla sundae topped with black currant sauce.	Icrecream with black currant sauce.	69	src/assets/images/Dessert/Black Currant sundae.png	dessert	Sundaes	veg	2	f	t	3	\N	\N	\N	f	\N
60	Chocolate Sundae	Creamy vanilla sundae topped with rich chocolate fudge.	Ice cream with hot chocolate fudge.	45	src/assets/images/Dessert/Chocolate sundae.png	dessert	Sundaes	veg	3	f	t	3	\N	\N	\N	f	\N
61	BK Fusion Sundae (made with KitKat)	Creamy vanilla sundae topped with crunchy KitKat pieces.	Creamy vanilla sundae topped with delicious KitKat pieces for the perfect chocolate crunch.	79	src/assets/images/Dessert/BK Fusion Sundae (made with KitKat).png	dessert	Sundaes	veg	4	f	t	3	\N	\N	\N	f	\N
62	Cookie Crunch Sundae	Chocolate sundae topped with crunchy cookie crumbs.	Ice cream with cookie crumb & hot chocolate fudge.	69	src/assets/images/Dessert/Cookie Crunch Sundae.png	dessert	Special Desserts	veg	1	f	t	4	\N	\N	\N	f	\N
63	Chocolate Mousse Cup	Smooth chocolate mousse topped with ganache and choco chips.	Airy and creamy chocolate mousse topped with chocolate ganache and choco chips.	129	src/assets/images/Dessert/Chocolate Mousse Cup.png	dessert	Special Desserts	veg	2	f	t	4	\N	\N	\N	f	\N
64	Choco Lava Cup	Soft chocolate cake with a rich molten center.	Melty Chocolate filled in cupcake.	119	src/assets/images/Dessert/Choco Lava Cup.png	dessert	Special Desserts	veg	3	f	t	4	\N	\N	\N	f	\N
65	Fries (Medium)	Golden crispy fries.	Perfectly salted golden potato fries, fried until crispy on the outside and fluffy on the inside. A classic side that pairs perfectly with any burger or beverage.	130	src/assets/images/sides/Fries (Medium).png	side	Fries	veg	1	f	t	1	\N	side	medium	f	\N
66	Fries (King)	Extra-large crispy fries.	A king-sized portion of golden crispy fries, seasoned to perfection and ideal for sharing or satisfying bigger cravings.	140	src/assets/images/sides/Fries (King).png	side	Fries	veg	2	f	t	1	\N	side	large	f	\N
71	(6Pc) Crunchy Chicken Nuggets + 1 Dip	6 crispy chicken nuggets served with 1 delicious dip.	Six juicy chicken nuggets wrapped in a crunchy coating and served hot for a delicious snack or side.	189	src/assets/images/sides/(6Pc) Crunchy Chicken Nuggets + 1 Dip.png	side	Nuggets	non veg	2	f	t	2	\N	\N	\N	f	\N
72	(9Pc) Crunchy Chicken Nuggets + 2 Dips	9 crispy chicken nuggets served with 2 delicious dips.	A generous serving of crispy chicken nuggets made with tender chicken and a crunchy golden crust.	309	src/assets/images/sides/(9Pc) Crunchy Chicken Nuggets + 2 Dips.png	side	Nuggets	non veg	3	f	t	2	\N	\N	\N	f	\N
73	(18Pc) Crunchy Chicken Nuggets + 3 Dips	18 crispy chicken nuggets served with 3 delicious dips.	Perfect for sharing, these crunchy chicken nuggets offer juicy chicken wrapped in a flavorful golden coating.	359	src/assets/images/sides/(18Pc) Crunchy Chicken Nuggets + 3 Dips.png	side	Nuggets	non veg	4	f	t	2	\N	\N	\N	f	\N
75	Peri Peri Chicken Nuggets 6 Pc	Crispy peri peri chicken bites with spicy sauce.	Tender Juicy Crunchy Chicken Nuggets fried to golden perfection topped with Peri Peri Glaze.	169	src/assets/images/sides/Peri Peri Chicken Nuggets 6 Pc.png	side	Nuggets	non veg	6	f	t	2	\N	\N	\N	f	\N
76	Peri Peri Chicken Wings 4pc	Spicy peri peri chicken wings with bold seasoning.	Chicken Wings dunked in hot and spicy peri peri glaze.	209	src/assets/images/sides/Peri Peri Chicken Wings 4pc.png	side	Nuggets	non veg	7	f	t	2	\N	\N	\N	f	\N
77	Peri Peri Chicken Boneless 4pc	Spicy peri peri chicken bites with rich seasoning.	Boneless chicken dunked in hot and spicy peri peri glaze.	199	src/assets/images/sides/Peri Peri Chicken Boneless 4pc.png	side	Nuggets	non veg	8	f	t	2	\N	\N	\N	f	\N
78	Peri Peri Chicken Boneless 7pc	Juicy peri peri chicken bites with bold spices.	Boneless chicken dunked in hot and spicy peri peri glaze.	309	src/assets/images/sides/Peri Peri Chicken Boneless 7pc.png	side	Nuggets	non veg	9	f	t	2	\N	\N	\N	f	\N
79	Chicken Wings - Fried (8 Pcs)	Crispy fried chicken bucket with golden crunch.	Juicy chicken wings cooked to perfection.	279	src/assets/images/sides/Chicken Wings - Fried (8 Pcs).png	side	Nuggets	non veg	10	f	t	2	\N	\N	\N	f	\N
53	KitKat Shake	Creamy KitKat blended thick shake.	Made with Kit Kat, enjoy our rich creamy fusion thick shake.Qty: 378ml| Kcal: 591 | Carbs: 92 gms| Sugar: 77 gms| Fat: 20 gms| Saturated fat: 15 gms| Protein: 10.6 gms| Sodium: 270 mg	249	src/assets/images/Drinks/KitKat Shake.png	drink	Shakes	veg	4	f	t	4	cold	drink	\N	f	\N
81	Veggie Strips (5 Pc)	5 crispy veggie strips.	Delicious vegetable strips coated in a crunchy golden crumb and fried until perfectly crisp.	55	src/assets/images/sides/Veggie Strips (5 Pc).png	side	Veggie Sides	veg	1	f	t	3	\N	\N	\N	f	\N
82	Masala Hashbrown	Crispy masala hashbrown.	Golden hashbrown infused with flavorful Indian spices and fried to crispy perfection.	45	src/assets/images/sides/Masala Hashbrown.png	side	Veggie Sides	veg	2	f	t	3	\N	\N	\N	f	\N
83	Fiery Hell Dip	Extra spicy dip.	A bold and fiery dipping sauce crafted for spice lovers who enjoy an intense burst of heat with every bite.	25	src/assets/images/sides/Fiery Hell Dip.png	side	Dips	veg	1	f	t	4	\N	\N	\N	f	\N
84	Chilli Sauce With Oregano	Classic chilli oregano dip.	A flavorful blend of chilli sauce and aromatic oregano that enhances the taste of fries, nuggets, and sides.	25	src/assets/images/sides/Chilli Sauce With Oregano.png	side	Dips	veg	2	f	t	4	\N	\N	\N	f	\N
5	Crispy Veg Double Patty	Double crispy veg patties with signature sauce.	Double up our best selling crispy veg burger	89	src/assets/images/Burgers/Crispy Veg Double Patty.png	burger	Value Burgers	veg	5	t	t	1	\N	main	\N	f	src/assets/images/Meals/Crispy Veg Double Patty meal.png
4	Veg Makhani	Veg patty with fresh onion & makhani sauce.	New Premium Black & White Sesame Bun with Veg Patty, Fresh Onion and Makhani Sauce.	69	src/assets/images/Burgers/Veg Makhani.png	burger	Value Burgers	veg	4	t	t	1	\N	main	\N	f	src/assets/images/Meals/Veg Makhani Burst Burger meal.png
85	Peri Peri Chicken Boneless 2 Pc	2 pieces of boneless peri peri chicken	2 pieces of boneless peri peri chicken coated with peri peri seasoning.	0	src/assets/images/sides/Peri Peri Chicken Nuggets 4 Pc.png	side	Nuggets	non_veg	11	f	t	2	\N	side	\N	t	\N
3	Chicken Makhani	Crispy chicken patty with rich makhani sauce.	New Premium Black and White Sesame Bun with Crispy Chicken Patty, Fresh Onion and Makhani Sauce. Qty: 125 gms | Kcal: 275 | Carbs: 35 gms | Sugar: 6 gms | Fat: 9 gms | Saturated fat: 4 gms | Protein: 13.3 gms | Sodium: 627 mg	89	src/assets/images/Burgers/Chicken Makhani.png	burger	Value Burgers	non veg	3	t	t	1	\N	main	\N	f	src/assets/images/Meals/Chicken Makhani Burst Burger meal.png
2	Crispy Chicken	Crispy chicken patty with onion & signature sauce.	New Premium Black & White Sesame Bun with Crispy Chicken Patty, Fresh Onion and Signature Sauce.Qty: 125 gms | Kcal: 299 | Carbs: 33 gms | Sugar: 5 gms | Fat: 13 gms | Saturated fat: 4 gms | Protein: 12.4 gms | Sodium: 405 mg	79	src/assets/images/Burgers/Crispy Chicken.png	burger	Value Burgers	non veg	2	t	t	1	\N	main	\N	f	src/assets/images/Meals/Crispy Chicken meal.png
1	Crispy Veg	Crispy veg patty with onion & signature sauce.	New Premium Black & White Sesame Bun with Crispy Veg Patty, Fresh Onion and Signature Sauce	59	src/assets/images/Burgers/Crispy Veg.png	burger	Value Burgers	veg	1	t	t	1	\N	main	\N	f	src/assets/images/Meals/Crispy Veg Meal.png
39	Tropical Fizz (Small)	Refreshing fizzy pineapple and lemon drink.	A refreshing fizzy drink with pineapple and lemon flavours making the perfect sweet-meets-tangy cooler. Qty: 300ml | Kcal: 34.25 | Carbs: 8.37 gms | Sugar: 8.29 gms | Fat: 0.05 gms | Saturated Fat: 0 gms | Protein: 0.08 gms | Sodium: 400.80 mg	99	src/assets/images/Drinks/Tropical Fizz.png	drink	Cold Drinks	veg	9	f	t	2	cold	drink		f	\N
46	Masala Fizz (Small)	Sparkling masala flavored fizzy drink.	A fizzy twist to your favourite Coke — now with full on Masala flavour.\nQty: 300ml| Kcal: 44.17 | Carbs: 11.04 gms| Sugar: 11.03 gms| Fat: 0.0 gms| Saturated fat: 0 gms| Protein: 0.0 gms| Sodium: 367.00 mg	99	src/assets/images/Drinks/Masala Fizz.png	drink	Cold Drinks	veg	9	f	t	2	cold	drink		f	\N
42	Tropical Fizz (Medium)	Refreshing fizzy pineapple and lemon drink.	A refreshing fizzy drink with pineapple and lemon flavours making the perfect sweet-meets-tangy cooler. Qty: 450ml | Kcal: 68.50 | Carbs: 16.74 gms | Sugar: 16.57 gms | Fat: 0.1 gms | Saturated Fat: 0 gms | Protein: 0.16 gms | Sodium: 801.6 mg	129	src/assets/images/Drinks/Tropical Fizz.png	drink	Cold Drinks	veg	8	f	t	2	cold	drink		f	\N
23	Peri Peri Chicken Burger	Spicy peri peri chicken burger with fresh vegetables.	Crispy Juicy whole-muscle chicken patty dunked in hot & spicy Peri Peri glaze with herby mayo in premium brioche bun for authentic Peri Peri flavours	229	src/assets/images/Burgers/Peri Peri Chicken Burger.png	burger	Peri Peri	non veg	5	t	t	6	\N	main	\N	f	src/assets/images/Meals/Peri Peri Chicken Burger meal.png
67	Peri Peri Fries (Medium)	Fries with peri peri seasoning.	Crispy golden fries tossed in a bold peri peri spice blend that delivers the perfect combination of heat and flavor.	149	src/assets/images/sides/Peri Peri Fries (Medium).png	side	Fries	veg	3	f	t	1	\N	side	medium	f	\N
68	Peri Peri Fries (King)	King-size peri peri fries.	A larger serving of crispy fries generously coated in spicy peri peri seasoning for an irresistible kick.	154	src/assets/images/sides/Peri Peri Fries (King).png	side	Fries	veg	4	f	t	1	\N	side	large	f	\N
69	Saucy Fries	Loaded fries with sauce.	Crunchy fries topped with Burger King's signature creamy sauce, creating a rich and indulgent snacking experience.	139	src/assets/images/sides/Saucy Fries.png	side	Fries	veg	5	f	t	1	\N	side	\N	f	\N
70	Crunchy Chicken Nuggets (4 Pc)	4 crispy chicken nuggets, golden and crunchy.	Tender chicken nuggets coated in a golden crunchy crumb and cooked to perfection for a satisfying bite every time.	89	src/assets/images/sides/Crunchy Chicken Nuggets (4 Pc).png	side	Nuggets	non veg	1	f	t	2	\N	side	\N	f	\N
74	Peri Peri Chicken Nuggets 4 Pc	Crispy peri peri chicken bites with spicy sauce.	Tender Juicy Crunchy Chicken Nuggets fried to golden perfection topped with Peri Peri Glaze.	109	src/assets/images/sides/Peri Peri Chicken Nuggets 4 Pc.png	side	Nuggets	non veg	5	f	t	2	\N	side	\N	f	\N
48	Cola Float	Classic cola with vanilla soft serve.	Coke + Ice Cream = Bliss.	52	src/assets/images/Drinks/Cola Float.png	drink	Floats	veg	1	f	t	3	cold	drink	\N	f	\N
49	Fanta Float	Refreshing Fanta with vanilla soft serve.	Fanta + Ice Cream = Bliss.	52	src/assets/images/Drinks/Fanta Float.png	drink	Floats	veg	2	f	t	3	cold	drink	\N	f	\N
50	Berry Blast Shake	Creamy black currant thick shake.	Rich Creamy Black Currant Thick shake.	189	src/assets/images/Drinks/Berry Blast Shake.png	drink	Shakes	veg	1	f	t	4	cold	drink	\N	f	\N
51	Mango Shake	Rich and creamy mango thick shake.	Rich Creamy Mango Thick shake.	189	src/assets/images/Drinks/Mango Shake.png	drink	Shakes	veg	2	f	t	4	cold	drink	\N	f	\N
52	Chocolate Shake	Rich and creamy chocolate thick shake.	Rich Creamy Chocolate Thick shake.	189	src/assets/images/Drinks/Chocolate Shake.png	drink	Shakes	veg	3	f	t	4	cold	drink	\N	f	\N
17	BK Veg Pizza Puff	Crispy puff with cheesy veggie pizza filling.	Crispy and flaky puff pastry loaded with a delicious pizza-style filling of rich tomato sauce, sweet corn, carrots, bell peppers, and melted cheesy goodness. Baked to golden perfection for a crunchy bite and authentic pizza flavors in every mouthful.	45	src/assets/images/Burgers/BK Veg Pizza Puff.png	burger	Wraps and Tacos	veg	3	t	t	5	\N	side	\N	f	src/assets/images/Meals/BK Veg Pizza Puff Meal.png
19	Peri Peri Veg	Spicy grilled veg burger with fresh vegetables.	XL size 7 layer Veg Whopper with crunchy veg patty dunked in hot & spicy Peri Peri glaze with herby mayo in premium glazed buns for authentic Peri Peri flavours	199	src/assets/images/Burgers/Peri Peri Veg.png	burger	Peri Peri	veg	1	t	t	6	\N	main	\N	f	src/assets/images/Meals/Peri Peri Veg Whopper meal.png
20	Peri Peri Chicken	Juicy grilled chicken burger with fresh vegetables.	XL size 7 layer Grill Chicken Whopper with grill chicken patty dunked in hot & spicy Peri Peri glaze with herby mayo in premium glazed buns for authentic Peri Peri flavours	239	src/assets/images/Burgers/Peri Peri Chicken.png	burger	Peri Peri	non veg	2	t	t	6	\N	main	\N	f	src/assets/images/Meals/Peri Peri Chicken Burger meal.png
18	Paneer Royale Wrap	Loaded wrap with paneer, veggies & sauces.	Loaded wrap with thick paneer patty, lots of veggies and sauces.Qty: 229 gms | Kcal: 406 | Carbs: 63 gms| Sugar: 18 gms| Fat: 33 gms| Saturated fat: 13 gms| Protein: 16.6 gms| Sodium: 763 mg	189	src/assets/images/Burgers/Paneer Royale Wrap.png	burger	Wraps and Tacos	veg	4	t	t	5	\N	main	\N	f	src/assets/images/Meals/Paneer Royale Wrap meal.png
16	Crunchy Chicken Taco	Crunchy taco with chicken patty & spicy sauce.	Crunchy Shell with chicken patty, crunchy veggies and spicy sauce.	99	src/assets/images/Burgers/Crunchy Chicken Taco.png	burger	Wraps and Tacos	non veg	2	t	t	5	\N	main	\N	f	src/assets/images/Meals/Crunchy Chicken Taco meal.png
15	Crunchy Veg Taco	Crunchy taco with beans, veggies & secret sauce.	Be ready for a crunchy, saucy, explosion. A crunchy taco shell filled with beans & veg mix, chef's secret sauce, fresh onion & crisp lettuce.	79	src/assets/images/Burgers/Crunchy Veg Taco src/assets/images/Burgers/Crunchy Veg Taco.png	burger	Wraps and Tacos	veg	1	t	t	5	\N	main	\N	f	src/assets/images/Meals/Crunchy Veg Taco meal.png
14	BK Chicken	Crunchy chicken patty with lettuce & mayo.	New Premium Black & White Sesame Bun with Crunchy Chicken Patty, Lettuce,Tomatoes(seasonal) & Our Signature Mayo.Qty: 163 gms | Kcal: 333 | Carbs: 41 gms| Sugar: 5 gms| Fat: 13 gms| Saturated fat: 5 gms| Protein: 13.7 gms| Sodium: 347 mg	139	src/assets/images/Burgers/BK Chicken.png	burger	Crazy Deals	non veg	2	t	t	4	\N	main	\N	f	src/assets/images/Meals/BK Chicken Burger meal.png
\.


--
-- Name: branches_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.branches_id_seq', 1, true);


--
-- Name: brands_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.brands_id_seq', 2, true);


--
-- Name: cross_sell_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.cross_sell_id_seq', 1, false);


--
-- Name: inventory_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.inventory_id_seq', 88, true);


--
-- Name: meal_defaults_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.meal_defaults_id_seq', 2, true);


--
-- Name: meal_upgrade_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.meal_upgrade_rules_id_seq', 174, true);


--
-- Name: menu_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.menu_items_id_seq', 85, true);


--
-- Name: branches branches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_pkey PRIMARY KEY (id);


--
-- Name: brands brands_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_name_key UNIQUE (name);


--
-- Name: brands brands_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (id);


--
-- Name: cross_sell cross_sell_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_sell
    ADD CONSTRAINT cross_sell_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: meal_defaults meal_defaults_meal_size_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_defaults
    ADD CONSTRAINT meal_defaults_meal_size_key UNIQUE (meal_size);


--
-- Name: meal_defaults meal_defaults_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_defaults
    ADD CONSTRAINT meal_defaults_pkey PRIMARY KEY (id);


--
-- Name: meal_upgrade_rules meal_upgrade_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_upgrade_rules
    ADD CONSTRAINT meal_upgrade_rules_pkey PRIMARY KEY (id);


--
-- Name: menu_items menu_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.menu_items
    ADD CONSTRAINT menu_items_pkey PRIMARY KEY (id);


--
-- Name: branches branches_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES public.brands(id);


--
-- Name: cross_sell cross_sell_recommended_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_sell
    ADD CONSTRAINT cross_sell_recommended_item_id_fkey FOREIGN KEY (recommended_item_id) REFERENCES public.menu_items(id);


--
-- Name: cross_sell cross_sell_source_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_sell
    ADD CONSTRAINT cross_sell_source_item_id_fkey FOREIGN KEY (source_item_id) REFERENCES public.menu_items(id);


--
-- Name: inventory inventory_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.branches(id);


--
-- Name: inventory inventory_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.menu_items(id);


--
-- Name: meal_defaults meal_defaults_default_drink_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_defaults
    ADD CONSTRAINT meal_defaults_default_drink_id_fkey FOREIGN KEY (default_drink_id) REFERENCES public.menu_items(id);


--
-- Name: meal_defaults meal_defaults_default_side_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_defaults
    ADD CONSTRAINT meal_defaults_default_side_id_fkey FOREIGN KEY (default_side_id) REFERENCES public.menu_items(id);


--
-- Name: meal_upgrade_rules meal_upgrade_rules_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meal_upgrade_rules
    ADD CONSTRAINT meal_upgrade_rules_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.menu_items(id);


--
-- PostgreSQL database dump complete
--

\unrestrict GGglollqtqpG92fltMQN4PTh1k0gu4zyvaqQcfybmDcWFazquct6XrZ8oZwqinF

