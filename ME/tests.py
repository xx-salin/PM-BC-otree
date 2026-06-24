from otree.api import Bot, Submission
from . import *

class PlayerBot(Bot):

    def play_round(self):

        if self.round_number == 1:

            yield Instructions0, {
                'prolific_id': 'A' * 24,
                'browser_first': 'Chrome',
                'leave': 0
            }

            yield AttentionCheck1, {
                'lines': 1
            }

            yield AttentionCheck2, {
                'cafewall': 2
            }

            yield Submission(AttentionCheckResult, check_html=False)

            yield Submission(Instructions1, check_html=False)
            yield Submission(Instructions2, check_html=False)

            yield ComprehensionTestPage, {
                'question_1': 1,
                'question_2': 0,
                'question_3': 1,
                'question_4': 0,
                'failures_per_q': 'test',
                'failed_comprehension_test': False,
            }

        # =========================
        # Treatment page
        # =========================
        yield AssetsPerformance, {
            'clicks': '[]',
            'refresh_count': 0
        }

        goal = self.player.participant.vars.get("goal_treatment")
        is_sell_treatment = goal in [1, 2, 5, 6, 9, 10, 13, 14]
        decision_payload = {'AssetToSell': 'A'} if is_sell_treatment else {'AssetToBuy': 'A'}

        prediction_payload = {
            'PredictionA': 5,
            'PredictionB': 5,
            'RiskA': 3,
            'RiskB': 3,
            'Confidence': 3,
        }

        # Even treatments: prediction first, then decision.
        if goal in [2, 4, 6, 8, 10, 12, 14, 16]:
            yield Task_ReturnPrediction_Early, prediction_payload
            yield Task_InvestmentDecision_Late, decision_payload
        else:
            # Odd treatments: decision first, then prediction.
            yield Task_InvestmentDecision, decision_payload
            yield Task_ReturnPrediction, prediction_payload

        yield Submission(Round_End, check_html=False)

        # =========================
        # Final round pages
        # =========================
        if self.round_number == Constants.num_rounds:

            yield AttentionCheck3, {
                'can': 'red'
            }

            yield AttentionCheck4, {
                'words': 'test'
            }

            yield Submission(BotScreening, check_html=False)

            if goal in [1, 3, 5, 7, 9, 11, 13, 15]:
                yield Survey1, {
                    'OtherInfoC': 'test'
                }
            else:
                yield Survey1, {
                    'OtherInfoB': 'test'
                }

            
            yield Survey2, {
                    'MuM': 3,
                    'MuC': 3,
                    'LastRetM': 3,
                    'LastRetC': 3,
                    'Outperform': 3,
                    'Riskiness': 3,
                    'Recency': 3,
                    
                }

            yield Survey3, {
                'Age': 30,
                'Sex': 2,
                'FinInterest': 3,
                'Investor': 1,
                'FinanceProf': 0,
                'RiskAffinity': 3,
            }

            yield FinalPaymentInformation, {
                'Satisfaction': 5,
                'OpenFeedback': 'Perfect'
            }

            yield Submission(LinkToProlific, check_html=False)
