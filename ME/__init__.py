from otree.api import *

import logging
import math
import random
import json

import numpy as np
import pandas
import ast
from decimal import Decimal, ROUND_HALF_UP
from django.utils.safestring import mark_safe
import os


logger = logging.getLogger(__name__)

# -------------------------------------
# Models page is used for backend development. Things that are displayed are coded in pages.py, often with the help of code from models.py
# -------------------------------------
author = 'MN'
doc = """

"""
# -------------------------------------
# Basic inputs (parameters, distribution)
# -------------------------------------
class Constants(BaseConstants):
    name_in_url = 'ME'
    players_per_group = None  # We rarely use groups. Player grouped with treatment keys
    num_rounds = 8  # how many rounds does a one player play
    num_months = 12  # 12 months
    
    begin_row = 1  # begin row in the excel

    pages_first_round = 7
    pages_last_round = 8
    pages_each_rounds = 4 

    total_pages = pages_first_round + pages_each_rounds * num_rounds + pages_last_round

  
    COMPLICATED_WORDS = ['Schadenfreude', 'Bourgeoisie', 'Worcestershire']

    # ===============================
    # MARGINAL RETURNS
    # ===============================
   

    BASE_DIR = os.path.dirname(__file__)
    monthly_file_path = os.path.join(BASE_DIR, 'Final_1600_Pairs.xlsx')
    cumulative_file_path = os.path.join(BASE_DIR, 'Final_1600_Pairs_Cumulative.xlsx')

    sheet = pandas.read_excel(
        monthly_file_path,
        sheet_name='Sheet1',
        engine='openpyxl'
    )

    sheet_cumulative = pandas.read_excel(
        cumulative_file_path,
        sheet_name='Sheet1',
        engine='openpyxl'
    )

    sheet = sheet.dropna(axis=0, how="all", inplace=False)
    sheet = sheet.dropna(axis=1, how="all", inplace=False)
    sheet_cumulative = sheet_cumulative.dropna(axis=0, how="all", inplace=False)
    sheet_cumulative = sheet_cumulative.dropna(axis=1, how="all", inplace=False)

    if len(sheet) != len(sheet_cumulative):
        raise ValueError(
            f"Monthly file rows ({len(sheet)}) and cumulative file rows ({len(sheet_cumulative)}) do not match"
        )

    num_distributions = len(sheet) // 2 # number of rows in the returns excel sheet

    # Explicitly define month columns
    month_columns = [f"M{i}" for i in range(1, 13)]


    distributions = {}

    for distr in range(num_distributions):

        # Read monthly returns at full precision; round only when displaying them
        row_A = sheet.iloc[distr * 2][month_columns].tolist()
        row_B = [0.0] * len(row_A)  # zero-interest cash account

        # NO RANDOMIZATION
        distributions[distr] = [row_A, row_B]


    

    # ============================
    # CUMULATIVE RETURNS (read directly from MATLAB-generated cumulative file)
    # ============================

    distributions_compound = {}

    for distr in range(num_distributions):

        row_A_cumulative = sheet_cumulative.iloc[distr * 2][month_columns].tolist()
        row_B_cumulative = [0.0] * len(row_A_cumulative)

        distributions_compound[distr] = [row_A_cumulative, row_B_cumulative]


    bonus_basefee = cu(2.5)
    prediction_bonus = cu(2.0)

    # Dicts with the questions and answers used in the experiment
    question_dict = ['BeliefsDependence_Mu1', 'BeliefsDependence_PLoss1']
    short_q_dict = ['the average return of the asset ']


# -------------------------------------
# Allocate treatments
# -------------------------------------
class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


# -------------------------------------
# Creating the database fields
# -------------------------------------
class Player(BasePlayer):
    pass
    # Treatment related ---------------------------------
    distribution_id = models.IntegerField()
    distribution = models.LongStringField()
    goal_treatment = models.IntegerField()
    color_treatment = models.IntegerField()  # 0=colored, 1=neutral
    # Payment related -----------------------------------
    paid_subsection = models.PositiveIntegerField()  # 1,..,or num_rounds to be paid
    clicks = models.LongStringField()
    # Other information --------------------------
    browser_first = models.CharField()
    leave = models.BooleanField(initial=False)
    # Attention checks -------------------------
    attention1 = models.IntegerField(initial=2)
    attention2 = models.IntegerField(initial=2)
    attention3 = models.IntegerField(initial=2)
    attention4 = models.IntegerField(initial=2)
    checks = models.IntegerField(initial=2)
    honolulu = models.StringField(
        label='Please type the word above into the space below:', max_length=8
    )

    can = models.StringField(
        label="What color is the can depicted above?",
        max_length=6
    )

    words = models.StringField(
    )
    lines = models.IntegerField(
        label="Which of the two lines above is longer?",
        choices=[[1, "Blue Line"],[2,"Red Line"],[3,"None (they are the same)"]],
        widget=widgets.RadioSelect(),
        
    )
    cafewall = models.IntegerField(
        label="Are all the gray lines above perfectly straight/horizontal or slanted/diagonal?",
        choices=[[1,"Straight/Horizontal"],[2,"Slanted/Diagonal"]],
        widget=widgets.RadioSelect(),
    )
    ComplicatedWord_Corrections = models.IntegerField(initial=0)
    AI_Test2 = models.StringField(label='', initial='[]')
    Survey1Timing = models.StringField(label='', initial='[]')
    # -------------------------------------
    # Comprehension
    # -------------------------------------
    question_1 = models.IntegerField(
        label='How many returns will you see for the investment asset?',
        choices=[
            [0, 'Six'],
            [1, 'Twelve'],
            [2, 'Twenty-four'],
        ],
        widget=widgets.RadioSelect(),
    )
    question_2 = models.IntegerField(
        label='What type of returns will you see for the investment asset?',
        choices=[
            [0, 'Monthly returns'],
            [1, 'Returns since purchase'],
            [2, 'Average returns'],
        ],
        widget=widgets.RadioSelect(),
    )   

    
    question_3 = models.IntegerField(
        label='After observing 12 months of the investment asset\'s performance, you will make… ...',
        choices=[

            [0, 'A sales decision'],
            [1, 'A repurchase decision'],
            [2, 'A return prediction'],
        ],
        widget=widgets.RadioSelect(),
    )
    question_4 = models.IntegerField(
    label='How is your bonus payment calculated?',
    choices=[
        [0, 'If I keep the investment asset, a return is simulated and my bonus is based on it. '
            'If I sell and move money to the cash account, my bonus is fixed at risk free 0% interest.'],
        [1, 'If I repurchase the investment asset, a return is simulated and my bonus is based on it. '
            'If I keep all money in the cash account, my bonus is fixed at risk free 0% interest.'],
        [2, 'The statistically correct expected value for the Investment Asset\'s monthly return will be used as a benchmark.\n '
            'I will receive a bonus based on how close my prediction is to this value.'],
    ],
    widget=widgets.RadioSelect(),
)
    
  
    failed_comprehension_test = models.BooleanField(initial=False)
   
    failures_per_q = models.LongStringField(default='the default text for the variable')

   
    # -------------------------------------
    # Treatments
    # -------------------------------------
    refresh_count = models.IntegerField()
    # -------------------------------------
    # Tasks - Investment decision(s) [Questions we ask from the player]
    # -------------------------------------

    AssetToSell = models.StringField(
    choices=[('A', 'Asset A'), ('B', 'Cash Account')],
    
    )
  
    AssetToBuy = models.StringField(
    choices=[('A', 'Asset A'), ('B', 'Cash Account')],
    
    )
    
 
    OtherInfoC = models.LongStringField(
        label='What information did you consider when making your investment decisions?', blank=True
    )

    OtherInfoB = models.LongStringField(
        label='What information did you consider when making your return predictions?', blank=True
    )

    PredictionA = models.FloatField(
        label='What do you expect the monthly return of Asset A to be next month? (in %, e.g., 5 for 5%)',
        min=-100, max=100
    )

    RiskA = models.FloatField(
        label='How risky is the asset A? ',
       
        initial=None,
    )

    Confidence = models.FloatField(  
        label='How confident you are about your predictions? ',
       
        initial=None,
       
    )
    
    # -------------------------------------
    # Directly after two rounds - Stuff related to payoff
    # -------------------------------------
    paid_input1 = models.CurrencyField()
    paid_input2 = models.CurrencyField()
    paid_asset = models.StringField(blank=True, choices=["A", "B"])
    paid_rendite = models.FloatField(blank=True)
    random_month = models.IntegerField(blank=True)
    prediction_asset = models.StringField(blank=True, choices=["A", "B"])
    predicted_return = models.FloatField(blank=True)
    actual_return = models.FloatField(blank=True)
    prediction_success = models.BooleanField(initial=False)
   
    
    MuM = models.IntegerField(
        initial=None,
        verbose_name='Did you rely on the &nbsp;<strong>average monthly return</strong>&nbsp; of assets?',
         choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - completely"]
       
        ],
        widget=widgets.RadioSelect(),
    )
    MuC = models.IntegerField(
        initial=None,
        verbose_name='Did you rely on the &nbsp;<strong>average return since purchase</strong>&nbsp; of assets?',
         choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - completely"]

        ],
        widget=widgets.RadioSelect(),
    )

    LastRetM = models.IntegerField(
        initial=None,
        verbose_name='Did you rely on the &nbsp;<strong>last monthly return</strong>&nbsp; of assets?',
         choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - completely"]
       
        ],
        widget=widgets.RadioSelect(),
    )
    LastRetC = models.IntegerField(
        initial=None,
        verbose_name='Did you rely on the &nbsp;<strong>last return since purchase</strong>&nbsp; of assets?',
         choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - completely"]
       
        ],
        widget=widgets.RadioSelect(),
    )

    Outperform = models.IntegerField(
        initial=None,
        verbose_name='Did you rely on &nbsp;<strong>how often</strong>&nbsp; one asset performed better than the other asset? ',
        choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - completely"]
            
        ],
        widget=widgets.RadioSelect(),
    )
    Riskiness = models.IntegerField(
        initial=None,
        verbose_name='Did you rely on the &nbsp;<strong>riskiness</strong>&nbsp; of the assets?',
        choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - completely"]

        ],
        widget=widgets.RadioSelect(),
    )
   
    Recency = models.IntegerField(
        initial=None,
            verbose_name='Did you rely more on the performance of the assets during the first half (Months 1-6) or the second half (Months 7-12) of the year?',
         choices=[
            [1, "1 - I overweighted Months 1-6"],
            [2, "2"],
            [3, "3 - I did not overweight either half of the year"],
            [4, "4"],
            [5, "5 - I overweighted Months 7-12"]
       
        ],
        widget=widgets.RadioSelect(),
    )
    
    # -----------------------------------------
    # Demographics / Questionnaire - Can partially already be asked before the start of treatments (helps analyze attrition later on)
    # -----------------------------------------
    Age = models.PositiveIntegerField(label='What is your age?', min=1, max=130)
    Sex = models.IntegerField(
        initial=None,
        choices=[
            [1, 'male'],
            [2, 'female'],
            [3, 'other'],
            [4, 'prefer not to say'],
        ],
        verbose_name='Are you male or female?',
        widget=widgets.RadioSelect(),
    )
    FinInterest = models.PositiveIntegerField(
        label='Are you interested in financial markets?',
        choices=[
            [1, "1 - not at all"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - very much"]
      
        ],
        initial=None,
        widget=widgets.RadioSelect(),
    )
    Investor = models.IntegerField(
        initial=None,
        label='Do you own stocks or mutual funds?',
        choices=[
            [0, 'no'],
            [1, 'yes'],
        ],
        widget=widgets.RadioSelect(),
    )
    FinanceProf = models.IntegerField(
        initial=None,
        label='Have you ever had a job in the financial industry?',
        choices=[
            [0, 'no'],
            [1, 'yes'],
        ],
         widget=widgets.RadioSelect(),
    )
    RiskAffinity = models.PositiveIntegerField(
        verbose_name='Please assess your willingness to take financial risks.',
        choices=[
            [1, "1 - not willing to take financial risks"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - willing to take large risks to achieve a significant gain"]
        ],
        initial=None,
        widget=widgets.RadioSelect(),
    )
   
    
    # -----------------------------------------
    # Final question (satisfaction, feedback...)
    # -----------------------------------------
    Satisfaction = models.PositiveIntegerField(
        verbose_name='How satisfied are you with your result? ',
         choices=[
            [1, "1 - very unsatisfied"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 - very satisfied"],
        ],
        initial=None,
        widget=widgets.RadioSelect(),
    )
    OpenFeedback = models.LongStringField(
        blank=True,
        label='Please briefly describe any feedback you might have on this study.',
    )
    # -----------------------------------------
    # Stuff related to Prolific, mTurk, or other platform used to run the experiment
    # -----------------------------------------
    prolific_id = models.StringField(blank=True, label='Your Prolific ID')
   
# Treatments:
# 1–4: Simple returns
# 5–8: Compound returns
#
# Treatments 1, 2, 5, 6 → Sell
# Treatments 3, 4, 7, 8 → Buy
#
# Treatments 1, 3, 5, 7 → Choice
# Treatments 2, 4, 6, 8 → Belief

#1,2,3,4,9,10,11,12 Monthly returns
#5,6,7,8,13,14,15,16 Cumulative returns

#1,2,5,6,9,10,13,14 Sell
#3,4,7,8,11,12,15,16 Buy

#1,3,5,7,9,11,13,15 Choice
#2,4,6,8,10,12,14,16 Belief

def creating_session(subsession: Subsession):

    if subsession.round_number == 1:

        for p in subsession.get_players():

            # Random paid round
            p.paid_subsection = random.randint(1, Constants.num_rounds)

            # Initialize storage
            p.participant.vars['distributions'] = []
            p.participant.vars['distribution_ids'] = []

            # Assign treatment 1–8
            treatment_key = (p.participant.id_in_session - 1) % 16 + 1
            p.participant.vars["goal_treatment"] = treatment_key
            p.goal_treatment = treatment_key

            # Assign color treatment (0=colored, 1=neutral)
            p.participant.vars["color_treatment"] = random.randint(0, 1)
            p.color_treatment = p.participant.vars["color_treatment"]

            # Select simple vs compound returns
            if p.goal_treatment in [1, 2, 3, 4, 9, 10, 11, 12]:  # simple returns
                distributions_to_use = Constants.distributions
            else:
                distributions_to_use = Constants.distributions_compound

            # Assign blocks of distributions
            start_row = ((p.participant.id_in_session - 1) // 16) * Constants.num_rounds

            for distr_id in range(start_row, start_row + Constants.num_rounds):
                p.participant.vars['distributions'].append(
                    distributions_to_use[distr_id]
                )
                p.participant.vars['distribution_ids'].append(distr_id)

    # Save distribution_id for current round
    for p in subsession.get_players():
        p.distribution_id = p.participant.vars['distribution_ids'][subsession.round_number - 1]
# -------------------------------------
# Groups not used in this experiment
# -------------------------------------

def set_payoffs(player: Player):

   

    goal_treatment = player.participant.vars["goal_treatment"]

    # ----------------------------
    # 1. Get chosen round
    # ----------------------------
    chosen_round = player.in_round(1).paid_subsection
    decision_player = player.in_round(chosen_round)

    # ----------------------------
    # 2. Select correct distribution
    # ----------------------------
    # For payoff ALWAYS use simple monthly returns, regardless of treatment
    distribution_id = player.participant.vars['distribution_ids'][chosen_round - 1]
    payoff_distribution = Constants.distributions[distribution_id]
    
    # (For display on AssetsPerformance, the page uses participant.vars which has the right compound/simple for that treatment)
    

    # ----------------------------
    # 3. Construct returns for A and B
    # ----------------------------
    returns_A = payoff_distribution[0]
    returns_B = payoff_distribution[1]

    # ----------------------------
    # 4. Draw one random month
    # ----------------------------
    month_index = random.randint(0, len(returns_A) - 1)

    # =========================================================
    # ================== CHOICE-BASED ==========================
    # Treatments: 1,3,5,7,9,11,13,15
    # =========================================================
    if goal_treatment in [1, 3, 5, 7, 9, 11, 13, 15]:

        # SELL treatments
        if goal_treatment in [1, 5, 9, 13]:
            if decision_player.AssetToSell == "A":
                invested_asset = "B"  # Kept asset (invested)
                realized_return = returns_B[month_index]
            else:
                invested_asset = "A"  # Kept asset (invested)
                realized_return = returns_A[month_index]

        # BUY treatments
        elif goal_treatment in [3, 7, 11, 15]:
            if decision_player.AssetToBuy == "A":
                invested_asset = "A"  # Bought asset (invested)
                realized_return = returns_A[month_index]
            else:
                invested_asset = "B"  # Bought asset (invested)
                realized_return = returns_B[month_index]

        realized_return = float(realized_return)  # FIX: avoid np.float64 being sent to Postgres on Heroku
        player.paid_asset = invested_asset
        player.paid_rendite = realized_return
        player.random_month = month_index + 1

        # Payoff rule
       
        #player.payoff = 1 * (1 + realized_return / 100)  # Assuming payoff is based on a 1 unit investment
        

        raw_payoff = 1 * (1 + realized_return / 100)
        player.payoff = float(Decimal(str(raw_payoff)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            

    # =========================================================
    # ================== BELIEF-BASED ==========================
    # Treatments: 2,4,6,8,10,12,14,16
    # =========================================================
    elif goal_treatment in [2, 4, 6, 8, 10, 12, 14, 16]:

        # Belief to evaluate
        pred_asset = "A"
        prediction = decision_player.PredictionA
        actual_return = float(sum(returns_A) / len(returns_A))

        player.prediction_asset = pred_asset
        player.predicted_return = prediction
        player.actual_return = actual_return
        if prediction is not None and actual_return is not None:
            player.prediction_success = bool(abs(prediction - actual_return) <= 0.3)
        else:
            player.prediction_success = False

        # Accuracy check (±0.3)
        player.payoff = 2.0 if player.prediction_success else 0.0

   
# PAGES
# -------------------------------------
# Welcome screens and instructions before the start of the experiment:
# -------------------------------------
class Instructions0(Page):
    template_name = 'ME/Instructions0.html'
    form_model = 'player'
    form_fields = ['browser_first', 'prolific_id','leave']

    @staticmethod
    def error_message(player: Player, value):
        if value['leave'] == 1:
            return None  # Skip validation if leave is clicked
        if not value['prolific_id']:
            return 'Please enter your Prolific ID. Currently, the ID field is empty'
        elif len(value['prolific_id']) != 24:
            id_len = len(value['prolific_id'])
            return 'You Prolific ID is not correct! The ID you inserted has {} characters. The Prolific ID is 24 characters long'.format(
                id_len
            )

    @staticmethod
    def vars_for_template(player: Player):
        if player.participant.vars["goal_treatment"] in [1, 3, 5, 7, 9, 11, 13, 15]:  # Choice-based treatments
            depends = 'an investment decision'
        else:
            depends = 'a return prediction'
        return {'depends': depends,
                 'testing': player.session.config["testing"]
                }

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1
    
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if player.leave == 1 :
            player.leave = True
    
    
class Leave(Page):
    template_name = 'ME/Leave.html'
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1  and player.leave
    def vars_for_template(player: Player):
        current_page = 1
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        return {
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages
        }
    
   


class PageA1(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        #answer1 = player.honolulu
        if player.lines == 1:
            player.attention1 = 1
        else:
            player.attention1 = 0

    form_model = 'player'
    form_fields = ['lines']

    def vars_for_template(player: Player):
        current_page = 2
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        return {
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages,
            'testing': player.session.config["testing"]
        }


class PageA2(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 

    @staticmethod
    def vars_for_template(player: Player):
        current_page = 3
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        return {
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages,
            'testing': player.session.config["testing"]
            }


    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.cafewall == 2:
            player.attention2 = 1
        else:
            player.attention2 = 0
        if player.attention1 == 1 and player.attention2 == 1:
            player.checks = 1
        else:
            player.checks = 0

    form_model = 'player'
    form_fields = ['cafewall']



class PageA3(Page):
    template_name = 'ME/PageA3.html'
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1 
    
    def vars_for_template(player: Player):
        current_page = 4
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        return {
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages
        }



# -------------------------------------
# Experiment:
# -------------------------------------
class Instructions1(Page):
    template_name = 'ME/Instructions1.html'
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1
    
    def vars_for_template(player: Player):
        current_page = 5
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        return {
            'percentage': rounded_percentage,
            'testing': player.session.config["testing"],
            'current_page': current_page,
            'total_pages':total_pages,
            'color_treatment': player.participant.vars["color_treatment"],
        }
    
class Instructions2(Page):
    template_name = 'ME/Instructions2.html'
    
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1
    
    def vars_for_template(player: Player):
        current_page = 6
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        fixed_return = None

        
        return {
            'percentage': rounded_percentage,
            'testing': player.session.config["testing"],
            'current_page': current_page,
            'total_pages':total_pages,
            'fixed_return': fixed_return,
            'var': player.participant.vars["goal_treatment"], 
        }


class ComprehensionTestPage(Page):
    form_model = 'player'
    form_fields = [
        'question_1',
        'question_2',
        'question_3',
        'question_4',
        'failures_per_q',
        'failed_comprehension_test',
    ]
    template_name = 'ME/ComprehensionTestPage.html'

    @staticmethod
    def vars_for_template(player: Player):

        current_page = 7
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        variable_for_2 = (player.participant.id_in_session - 1) % 16 + 1

        # Dynamic question 1 label depending on treatment (simple vs compound returns)
        # if variable_for_2 in [1,3,9,11]:
        #     question_1_label = 'How many monthly returns will you see for each asset before making your investment decision?'
        # elif variable_for_2 in [2,4,10,12]:
        #     question_1_label = 'How many monthly returns will you see for each asset before making your return prediction?'
        # elif variable_for_2 in [5,7,13,15]:
        #     question_1_label = 'How many returns since purchase will you see for each asset before making your investment decision?'    
        # elif variable_for_2 in [6,8,14,16]:
        #     question_1_label = 'How many returns since purchase will you see for each asset before making your return prediction?'


        return {
            'variable_for_2': variable_for_2,
            'testing': player.session.config["testing"],
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages': total_pages,
            #'question_1_label': question_1_label,
        }
    
    @staticmethod
    def js_vars(player):
        return dict(
               variable_for_2 = (player.participant.id_in_session - 1) % 16 + 1,
               participant_id = player.participant.id_in_session   
    )


    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1




class AssetsPerformance(Page):

    form_model = 'player'
    form_fields = ['clicks', 'refresh_count']

    template_name = 'ME/AssetsPerformance.html'

    @staticmethod
    def vars_for_template(player: Player):

        # Progress bar logic (keep if you still use it)
        current_page = 8 + (4 * (player.round_number - 1))
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        var = player.participant.vars.get('goal_treatment')
        color_treatment = player.participant.vars.get('color_treatment')

        # Get distribution for this round
        distr = player.participant.vars['distributions'][player.round_number - 1]

        asset_a = distr[0]  # 12 monthly returns
        asset_b = distr[1]

        # Convert to percentage for display (round to 1 decimal for monthly and compound returns)
        # Use Decimal.quantize with ROUND_HALF_UP for proper rounding (not banker's rounding)
        asset_a_pct = [float(Decimal(str(x)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)) for x in asset_a]
        asset_b_pct = [float(Decimal(str(x)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)) for x in asset_b]

        return {
            'percentage': rounded_percentage,
            'testing': player.session.config["testing"],
            'current_page': current_page,
            'total_pages': total_pages,
            'asset_a': asset_a_pct,
            'asset_b': asset_b_pct,
            'var': var,
            'color_treatment': color_treatment,
        }

    @staticmethod
    def js_vars(player):

        distr = player.participant.vars['distributions'][player.round_number - 1]
        

        return dict(
            asset_a=[float(Decimal(str(x)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)) for x in distr[0]],
            asset_b=[float(Decimal(str(x)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)) for x in distr[1]],
            roundnumber=player.round_number,
            participant_id=player.participant.id_in_session,
            goal_treatment=player.participant.vars.get('goal_treatment'),
            color_treatment=player.participant.vars.get('color_treatment'),
        )


 
class Task_InvestmentDecision(Page):

    template_name = 'ME/Task_InvestmentDecision.html'
    form_model = 'player'
    #form_fields = ['AssetToSell']
    @staticmethod
    def is_displayed(player: Player):
        return player.participant.vars.get('goal_treatment') in [1, 3, 5, 7, 9, 11, 13, 15]


    @staticmethod
    def get_form_fields(player: Player):
        var = player.participant.vars.get('goal_treatment')
        if var in [1, 2, 5, 6, 9, 10, 13, 14]:  # Sell treatments
            return ['AssetToSell']
        else:
            return ['AssetToBuy']

    @staticmethod
    def vars_for_template(player: Player):

        current_page = 9 + (4 * (player.round_number - 1))
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        var = player.participant.vars.get('goal_treatment')
        is_sell = var in [1, 2, 5, 6, 9, 10, 13, 14]


        return {
            'testing': player.session.config["testing"],
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages': total_pages,
            'is_sell': is_sell,
            'var': var,
        }
    
    @staticmethod
    def js_vars(player):
        var = player.participant.vars.get('goal_treatment')
        return dict(
            round_number=player.round_number,
            is_sell=var in [1, 2, 5, 6, 9, 10, 13, 14]
        )

    @staticmethod
    def error_message(player: Player, values):
        var = player.participant.vars.get('goal_treatment')
        if var in [1, 2, 5, 6, 9, 10, 13, 14]:
            if not values.get("AssetToSell"):
                return "Please select one asset to sell."
        else:
            if not values.get("AssetToBuy"):
                return "Please select one asset to buy."





class Task_ReturnPrediction(Page):

    template_name = 'ME/Task_ReturnPrediction.html'
    form_model = 'player'
    form_fields = ['PredictionA', 'RiskA', 'Confidence']

    @staticmethod
    def is_displayed(player: Player):
        return player.participant.vars.get('goal_treatment') in [1, 3, 5, 7, 9, 11, 13, 15]

    @staticmethod
    def vars_for_template(player: Player):

        current_page = 10 + (4 * (player.round_number - 1))
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        var = player.participant.vars.get('goal_treatment')

        return {
            'testing': player.session.config["testing"],
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages': total_pages,
            'var': var,
        }

    @staticmethod
    def js_vars(player):
        return dict(
            round_number=player.round_number,
        )

    @staticmethod
    def error_message(player: Player, values):
        errors = []
        if values.get("PredictionA") is None:
            errors.append("Please provide a prediction for Asset A.")
        if values.get("RiskA") is None:
            errors.append("Please assess the risk of Asset A.")
        if values.get("Confidence") is None:
            errors.append("Please indicate your confidence level.")

        if errors:
            return " ".join(errors)

class Task_ReturnPrediction_Early(Task_ReturnPrediction):
    @staticmethod
    def is_displayed(player: Player):
        return player.participant.vars.get('goal_treatment') in [2, 4, 6, 8, 10, 12, 14, 16]

class Task_InvestmentDecision_Late(Task_InvestmentDecision):
    @staticmethod
    def is_displayed(player: Player):
        return player.participant.vars.get('goal_treatment') in [2, 4, 6, 8, 10, 12, 14, 16]
    


class Round_End(Page):
    template_name = 'ME/Round_End.html'
    form_model = 'player'
  
    @staticmethod
    def vars_for_template(player: Player):

        current_page = 11 + (4 * (player.round_number - 1))
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        a = player.field_maybe_none('clicks')
        goal_treatment = player.participant.vars["goal_treatment"]
        
     
        return {
            'var': goal_treatment,
            'testing': player.session.config["testing"],
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages,
            'clicks': a,
        }
    @staticmethod
    def js_vars(player):
        return dict(
               round_number = player.round_number    
    )



# -------------------------------------
# Bot and AI checks after experiment:
# --------------------------------------

class PageB1(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == Constants.num_rounds

    @staticmethod
    def vars_for_template(player: Player):
        current_page = 40
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

    
        return {
                'percentage': rounded_percentage,
                'current_page': current_page,
                'total_pages':total_pages,
                'testing': player.session.config["testing"],
                }

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        answer1 = player.can
        if answer1.upper() == "RED":
            player.attention3 = 1
        else:
            player.attention3 = 0

    form_model = 'player'
    form_fields = ['can']


class PageB2(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == Constants.num_rounds


    def vars_for_template(player: Player):
        current_page = 41
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        insertWord = ', '.join(Constants.COMPLICATED_WORDS)


        return {
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages,
            'testing': player.session.config["testing"],
            'insertWord': insertWord,
        }
    @staticmethod
    def live_method(player, data):
        tmpEntry = ast.literal_eval(player.AI_Test2)
        tmpEntry.append(data[0])
        player.AI_Test2 = str(tmpEntry)

        if data[1].startswith("delete"):
            print('delete')
            player.ComplicatedWord_Corrections += 1
            print(player.ComplicatedWord_Corrections)

    form_model = 'player'
    form_fields = ['words']




class BotScreening(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == Constants.num_rounds 

    def vars_for_template(player: Player):
        current_page = 42
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        return {
            'percentage': rounded_percentage,
            'current_page': current_page,
            'total_pages':total_pages
        }


#------------------------------------------
class Survey1(Page):
    template_name = 'ME/Survey1.html'
    form_model = 'player'

    @staticmethod
    def get_form_fields(player: Player):
        goal_treatment = player.participant.vars.get('goal_treatment')
        if goal_treatment in [1, 3, 5, 7, 9, 11, 13, 15]:  # Choice-based treatments
            return ['OtherInfoC']
        return ['OtherInfoB']

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.round_number == Constants.num_rounds
        )
    
    @staticmethod
    def live_method(player, data):
        tmpTiming = json.loads(player.Survey1Timing)
        tmpTiming.append(data)
        player.Survey1Timing = json.dumps(tmpTiming)
    
    def vars_for_template(player: Player):

        current_page = 10 + (4 * Constants.num_rounds) + 1
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        return {
             'percentage': rounded_percentage,
             'testing': player.session.config["testing"],
             'current_page': current_page,
             'total_pages':total_pages,
             'goal_treatment': player.participant.vars.get('goal_treatment'),
        }


# -------------------------------------
# Questionnaire after experiment:
# -------------------------------------
class Survey2(Page):
    template_name = 'ME/Survey2.html'
    form_model = 'player'

    @staticmethod
    def get_form_fields(player: Player):
        goal_treatment = player.participant.vars.get('goal_treatment')
        return ['MuM', 'MuC','LastRetM','LastRetC', 'Outperform', 'Riskiness', 'Recency']

    @staticmethod
    def is_displayed(player: Player):
        return (
           
            player.round_number == Constants.num_rounds
        )
    @staticmethod
    def vars_for_template(player: Player):

        current_page = 10 + (4 * Constants.num_rounds) + 2
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        var = player.participant.vars.get('goal_treatment')


        return {
                'testing': player.session.config["testing"],
                'percentage': rounded_percentage,
                'current_page': current_page,
                'total_pages':total_pages,
                'field_names': Survey2.get_form_fields(player),
                'var': var,
                }


   


class Survey3(Page):
    template_name = 'ME/Survey3.html'
    form_model = 'player'
    form_fields = [
        'Age',
        'Sex',
        'FinInterest',
        'Investor',
        'FinanceProf',
        'RiskAffinity',
    ]
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        set_payoffs(player)

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == Constants.num_rounds
    
    @staticmethod
    def vars_for_template(player: Player):

        current_page = 10 + (4 * Constants.num_rounds) + 3
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        return {
                'testing': player.session.config["testing"],
                'percentage': rounded_percentage,
                'current_page': current_page,
                'total_pages':total_pages
                }



# -------------------------------------
# Payment and link to Prolific:
# -------------------------------------
class FinalPaymentInformation(Page):
    template_name = 'ME/FinalPaymentInformation.html'
    form_model = 'player'
    form_fields = ['Satisfaction', 'OpenFeedback']

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == Constants.num_rounds

    @staticmethod
    def vars_for_template(player: Player):

        current_page = 10 + (4 * Constants.num_rounds) + 4
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)
        bonus_basefee = Constants.bonus_basefee
        prediction_bonus = Constants.prediction_bonus
        payoff_val = player.payoff
        
        
        

        goal_treatment = player.participant.vars["goal_treatment"]
        is_choice_treatment = goal_treatment in [1, 3, 5, 7, 9, 11, 13, 15]
        is_belief_treatment = goal_treatment in [2, 4, 6, 8, 10, 12, 14, 16]
        paid_round_player = player.in_round(player.in_round(1).paid_subsection)
        sold_asset = None

        realized_return_display = None
        realized_return_abs_display = None
        predicted_return_display = None
        actual_return_display = None

        if is_choice_treatment:
            paid_rendite_value = player.field_maybe_none('paid_rendite')
            if paid_rendite_value is not None:
                realized_return_display = f"{paid_rendite_value:.1f}%"
                realized_return_abs_display = f"{abs(paid_rendite_value):.1f}%"

            if goal_treatment in [1, 5, 9, 13]:
                sold_asset = paid_round_player.field_maybe_none('AssetToSell')

        elif is_belief_treatment:
            predicted_return_value = player.field_maybe_none('predicted_return')
            if predicted_return_value is not None:
                predicted_return_display = f"{predicted_return_value:.1f}%"

            actual_return_value = player.field_maybe_none('actual_return')
            if actual_return_value is not None:
                actual_return_display = f"{actual_return_value:.1f}%"

        total_pay = bonus_basefee + payoff_val
        fixed_return = None
        formatted_fix_return = None

        return {
            'runde': player.in_round(1).paid_subsection,
            'paid_asset': player.field_maybe_none('paid_asset'),
            'sold_asset': sold_asset,
            'random_month': player.field_maybe_none('random_month'),
            'realized_return': player.field_maybe_none('paid_rendite'),
            'realized_return_display': realized_return_display,
            'realized_return_abs_display': realized_return_abs_display,
            'prediction_asset': player.field_maybe_none('prediction_asset'),
            'predicted_return': player.field_maybe_none('predicted_return'),
            'predicted_return_display': predicted_return_display,
            'actual_return': player.field_maybe_none('actual_return'),
            'actual_return_display': actual_return_display,
            'prediction_success': player.prediction_success,
            'prediction_threshold': 0.3,
            'payoff': payoff_val,
            'total_pay': total_pay,
            'goal_treatment': player.participant.vars["goal_treatment"],
            'random_question_round': player.in_round(1).paid_subsection,
            'percentage': rounded_percentage,
            'testing': player.session.config["testing"],
            'current_page': current_page,
            'total_pages':total_pages,
            'bonus_basefee': bonus_basefee,
            'prediction_bonus': prediction_bonus,
        }
    
        


class LinkToProlific(Page):
    template_name = 'ME/LinkToProlific.html'

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == Constants.num_rounds
    
    def vars_for_template(player: Player):

        current_page = 10 + (4 * Constants.num_rounds) + 5
        total_pages = Constants.total_pages
        percentage = (current_page / total_pages) * 100
        rounded_percentage = math.ceil(percentage)

        return {
                'percentage': rounded_percentage,
                'testing': player.session.config["testing"],
                'current_page': current_page,
                'total_pages':total_pages
                }


# -------------------------------------
# Page sequence
# -------------------------------------
page_sequence = (
    Instructions0,
    Leave,
    PageA1,
    PageA2,
    PageA3,
    Instructions1,
    Instructions2,
    ComprehensionTestPage,
    AssetsPerformance,
    Task_ReturnPrediction_Early,   # belief group: prediction first
    Task_InvestmentDecision_Late,  # belief group: decision second
    Task_InvestmentDecision,
    Task_ReturnPrediction,
    Round_End,
    PageB1,
    PageB2,
    BotScreening,
    Survey1,
    Survey2,
    Survey3,
    FinalPaymentInformation,
    LinkToProlific,
)

