from pysmt.fnode import FNode

from Analyzer.analyzer import check_property_refining, clear_all
from Analyzer.proof_reader import check_and_minimize
from Analyzer.type_constructor import create_type, create_action, union
from Analyzer.sleecOp import WhenRule, happen_within, otherwise, unless, complie_measure, Concern
from Analyzer.logic_operator import *
from Analyzer.proof_reader import Fact

from textx import metamodel_from_file, textx_isinstance

grammar_file = "sleec-gramar.tx"
mm = metamodel_from_file(grammar_file)
constants = {}

VOL_BOUND = 10

def isXinstance(obj, cls):
    return textx_isinstance(obj, mm[cls])


def read_model_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

    # Create a metamodel from the grammar file


def parse_event_def(event, type_dict):
    # DressingStarted = create_action("DressingStarted", [("time", "time")], type_dict)
    return create_action(event.name, [("time", "time")], type_dict)


def match_default_sleec_data_type(typename):
    if typename == "numeric":
        return "int"
    elif typename == "boolean":
        return "bool"
    else:
        return None


scalar_type = {}
registered_type = set()


def add_scale(scalePaarams):
    sps = scalePaarams.scaleParams
    for index in range(len(sps)):
        sp = sps[index]
        assert sp.name not in scalar_type
        scalar_type[sp.name] = index


def process_scalar(measure, type_dict):
    if measure.name not in registered_type:
        scalar = measure.type
        add_scale(measure.type)
        create_type(measure.name, type_dict, upper_bound=len(scalar.scaleParams) - 1, lower_bound=0)
        registered_type.add(measure.name)

    return measure.name, measure.name


def parse_measure_def(measure, type_dict):
    if isXinstance(measure, "ScalarMeasure"):
        return process_scalar(measure, type_dict)
    else:
        return measure.name, match_default_sleec_data_type(measure.type)


def parse_constants(constant, constants):
    value = constant.value
    if value.value:
        cur_val = value.value
    else:
        cur_val = parse_constants(value.constant, constants)
    if constant.name not in constants:
        constants[constant.name] = cur_val
    return cur_val


def parse_definitions(defs):
    ACTION_Mapping = {}
    _measures = [("time", "time")]
    type_dict = dict()

    # create the default types
    create_type("time", type_dict, lower_bound=0)
    create_type("int", type_dict)
    create_type("bool", type_dict, var_type=BOOL)

    for d in defs:
        if isXinstance(d, "Event"):
            ACTION_Mapping[d.name] = parse_event_def(d, type_dict)
        if isXinstance(d, "Measure"):
            _measures.append(parse_measure_def(d, type_dict))
        if isXinstance(d, "Constant"):
            parse_constants(d, constants)

    # Now, we should create the measure class
    ACTION_Mapping["Measure"] = create_action("Measure", _measures, type_dict)
    complie_measure(ACTION_Mapping["Measure"])
    return ACTION_Mapping


def parse_rules(rb, Action_Mapping):
    rules = []
    for r in rb.rules:
        rules.append(parse_element(r, Action_Mapping))
    return rules

def parse_concerns(rb, Action_Mapping):
    concerns = []
    for c in rb.concerns:
        concerns.append(parse_element(c, Action_Mapping))
    return concerns


def parse_element(node, Action_Mapping, head=None, measure=None):
    if isinstance(node, int) or isinstance(node, str):
        return node
    if node is None:
        return node
    if node == []:
        return None
    if isXinstance(node, "Rule"):
        res= parse_rule(node, Action_Mapping, head, measure, is_concern = False)
    elif isXinstance(node, "Concern"):
        res = parse_rule(node, Action_Mapping, head, measure, is_concern = True)
    elif isXinstance(node, "Trigger"):
        res = parse_trigger(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Event"):
        res = parse_event(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Response") or isXinstance(node, "InnerResponse"):
        res = parse_response(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Occ"):
        res = parse_occ(node, Action_Mapping, head, measure)
    elif isXinstance(node, "TimeLimit"):
        res = parse_timelimit(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Value"):
        res = parse_value(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Alternative"):
        res = parse_response(node.response, Action_Mapping, head, measure)
    elif isXinstance(node, "NumTerminal"):
        res= parse_numterminal(node, Action_Mapping, head, measure)
    elif isXinstance(node, "NumMeasure"):
        res = parse_num_measure(node, Action_Mapping, head, measure)
    elif isXinstance(node, "BoolMeasure"):
        res = parse_bool_measure(node, Action_Mapping, head, measure)
    elif isXinstance(node, "ScalarMeasure"):
        res = parse_scalar_measure(node, Action_Mapping, head, measure)
    elif isXinstance(node, "NumericalOp"):
        res = parse_num_op(node, Action_Mapping, head, measure)
    elif isXinstance(node, "BoolBinaryOp"):
        res = parse_bool_bin_op(node, Action_Mapping, head, measure)
    elif isXinstance(node, "NumBinOp"):
        res = parse_num_bin_op(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Defeater"):
        res = parse_defeater(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Negation"):
        res = parse_negation(node, Action_Mapping, head, measure)
    elif isXinstance(node, "ScalarBinaryOp"):
        res = parse_scalar_binary_op(node, Action_Mapping, head, measure)
    elif isXinstance(node, "ScalarTerminal"):
        res = parse_scalar_terminal(node, Action_Mapping, head, measure)
    elif isXinstance(node, "ScaleParam"):
        res = parse_scale_param(node, Action_Mapping, head, measure)
    elif isXinstance(node, "BoolTerminal"):
        res = parse_bool_terminal(node, Action_Mapping, head, measure)
    elif isXinstance(node, "Constant"):
        res = parse_value(node.value, Action_Mapping, head, measure)
    elif isXinstance(node, "TimeValue"):
        res = parse_timevalue(node, Action_Mapping, head, measure)
    else:
        assert False

    return res




def parse_rule(node, Action_Mapping, head, measure, is_concern = False):
    trigger = parse_element(node.trigger, Action_Mapping, head, measure)
    if node.condition is not None:
        condition = lambda h, m, node=node, Action_Mapping=Action_Mapping: \
            parse_element(node.condition, Action_Mapping, h, m)
    else:
        condition = None

    if not is_concern or node.response:
        response = lambda h, m, node=node, Action_Mapping=Action_Mapping: \
            parse_element(node.response, Action_Mapping, h, m)
    else:
        response = lambda h, m, node=node, Action_Mapping=Action_Mapping: \
            TRUE()
    if is_concern:
        return Concern(trigger, action=response, rule_condition=condition, reference=node)
    else:
        return WhenRule(trigger, action=response, rule_condition=condition, reference=node)


def parse_scale_param(node, Action_Mapping, head, measure):
    return scalar_type[node.name]


def parse_trigger(node, Action_Mapping, head, measure):
    return parse_element(node.event, Action_Mapping, head, measure)


def parse_event(node, Action_Mapping, head, measure):
    return Action_Mapping[node.name]


def parse_response(node, Action_Mapping, head, measure):
    occ = parse_element(node.occ, Action_Mapping, head, measure)
    alt = parse_element(node.alternative, Action_Mapping, head, measure)
    defeaters = [parse_element(defeater, Action_Mapping, head, measure) for defeater in node.defeater]
    if alt:
        main_action = otherwise(TRUE(), occ, alt)
    else:
        main_action = occ

    if not defeaters:
        return main_action
    else:
        return unless([(TRUE(), main_action)] + defeaters, reference=node)


def parse_occ(node, Action_Mapping, head, measure):
    negation = node.neg
    event = parse_element(node.event, Action_Mapping, head, measure)
    if node.limit:
        start, end = parse_element(node.limit, Action_Mapping, head, measure)
    else:
        start = end = 0

    if not node.limit:
        if node.inf:
            start = end = -1
        else:
            start = end = 0
    res = happen_within(event, head, start, end, ref=node)
    if negation:
        return NOT(res)
    else:
        return res

def parse_timevalue(node, Action_Mapping, head, measure):
    if node.unit == "seconds":
        mul = 1
    elif node.unit == "minutes":
        mul = 60
    elif node.unit == "hours":
        mul = 3600
    elif node.unit == "days":
        mul = 3600 * 24
    else:
        print("invalid time unit")
        assert False
    return mul * parse_element(node.value, Action_Mapping, head, measure)

def parse_timelimit(node, Action_Mapping, head, measure):
    if node.start:
        start = parse_element(node.start, Action_Mapping, head, measure)
    else:
        start = 0

    if node.end:
        end = parse_element(node.end, Action_Mapping, head, measure)
    else:
        end = 0
    return start, end


def parse_value(node, Action_Mapping, head, measure):
    if node.value is not None:
        return node.value
    else:
        return constants[node.constant]


def parse_numterminal(node, Action_Mapping, head, measure):
    if node.value is not None:
        return parse_element(node.value, Action_Mapping, head, measure)
    else:
        return parse_element(node.ID, Action_Mapping, head, measure)


def parse_scalar_terminal(node, Action_Mapping, head, measure):
    if node.value is not None:
        return parse_element(node.value, Action_Mapping, head, measure)
    else:
        return parse_element(node.ID, Action_Mapping, head, measure)


def parse_bool_terminal(node, Action_Mapping, head, measure):
    if node.value is not None:
        res = parse_element(node.value, Action_Mapping, head, measure)
    else:
        res = parse_element(node.ID, Action_Mapping, head, measure)

    if isinstance(res, FNode):
        res = Bool_Terminal(res)
        text_ref[res] = node

    return res


def parse_num_measure(node, Action_Mapping, head, measure):
    return getattr(measure, node.name)


def parse_bool_measure(node, Action_Mapping, head, measure):
    return getattr(measure, node.name)


def parse_scalar_measure(node, Action_Mapping, head, measure):
    return getattr(measure, node.name)


def parse_num_op(node, Action_Mapping, head, measure):
    lhs = parse_element(node.lhs, Action_Mapping, head, measure)
    rhs = parse_element(node.rhs, Action_Mapping, head, measure)
    func = op_str_sleec(node.op)
    res = func(lhs, rhs)
    if isinstance(res, FNode):
        res = Bool_Terminal(res)
        text_ref[res] = node
    return res


def parse_scalar_binary_op(node, Action_Mapping, head, measure):
    lhs = parse_element(node.lhs, Action_Mapping, head, measure)
    rhs = parse_element(node.rhs, Action_Mapping, head, measure)
    func = op_str_sleec(node.op)
    res = func(lhs, rhs)
    if isinstance(res, FNode):
        res = Bool_Terminal(res)
        text_ref[res] = node
    return res


def parse_bool_bin_op(node, Action_Mapping, head, measure):
    lhs = parse_element(node.lhs, Action_Mapping, head, measure)
    rhs = parse_element(node.rhs, Action_Mapping, head, measure)
    if node.op == "and":
        return AND(lhs, rhs)
    elif node.op == "or":
        return OR(lhs, rhs)
    else:
        assert False


def parse_num_bin_op(node, Action_Mapping, head, measure):
    lhs = parse_element(node.lhs, Action_Mapping, head, measure)
    rhs = parse_element(node.rhs, Action_Mapping, head, measure)
    func = op_str_sleec(node.op)
    return func(lhs, rhs)


def parse_defeater(node, Action_Mapping, head, measure):
    expr = parse_element(node.expr, Action_Mapping, head, measure)
    response = parse_element(node.response, Action_Mapping, head, measure)
    if response is None:
        return (expr, TRUE())
    else:
        return (expr, response)


def parse_negation(node, Action_Mapping, head, measure):
    return NOT(parse_element(node.expr, Action_Mapping, head, measure))


def check_concerns(model, rules, concerns, Action_Mapping, Actions, model_str="", to_print= True):
    Measure = Action_Mapping["Measure"]
    measure_inv = forall([Measure, Measure], lambda m1, m2: Implication(EQ(m1.time, m2.time), EQ(m1, m2)))
    output = ""
    adj_hl = []
    concern_raised = False

    for i in range(len(concerns)):
        if to_print:
            print("check concern_{}".format(i + 1))
        else:
            output += "check concern_{}\n".format(i + 1)

        concern = concerns[i]
        res = check_property_refining(concern.get_concern(), set(), [r.get_rule() for r in rules] + [measure_inv],
                                      Actions, [], True,
                                      min_solution=False,
                                      final_min_solution=True, restart=False, boundary_case=False,
                                      universal_blocking=False, vol_bound=VOL_BOUND
                                      )
        if isinstance(res, str):
            concern_raised = True
            if to_print:
                print("Concern is raised")

            concern_node = model.concernBlock.concerns[i]
            start, end = concern_node._tx_position, concern_node._tx_position_end
            output += "{}\n".format(model_str[start: end])
            output += "Concern is raised\n"
            output += res
            output += ("-" * 100 + '\n')
        elif res == -1:
            if to_print:
                print("Likely not raised")
            else:
                output += "Likely not raised\n"

        else:
            print("concern not raised")

        clear_all(Actions)
        reset_rules(rules)
        measure_inv.clear()
        derivation_rule.reset()
        print("*" * 100)
        output += "*" * 100 + '\n'
    return concern_raised, output, adj_hl


def check_conflict(model, rules, Action_Mapping, Actions, model_str="", check_proof=False, to_print= True):
    Measure = Action_Mapping["Measure"]
    measure_inv = forall([Measure, Measure], lambda m1, m2: Implication(EQ(m1.time, m2.time), EQ(m1, m2)))
    output = ""
    adj_hl = []
    conflict_res = False
    conflicting_set = set()

    for i in range(len(rules)):
        if to_print:
            print("check rule_{}".format(i + 1))
        else:
            output += "check rule_{}\n".format(i + 1)

        if i in conflicting_set:
            # if we have determined that i is in conflict with others:
            output += "Conflicting SLEEC rule:\n"
            target = model.ruleBlock.rules[i]
            start, end = target._tx_position, target._tx_position_end
            output += "{}\n".format(model_str[start: end])
            output += "Since it was mentioned in other conflict reported above:\n"
            output += "*" * 100 + '\n'
            continue

        rule = rules[i]
        res = check_property_refining(rule.get_premise(), set(), [r.get_rule() for r in rules] + [measure_inv],
                                      Actions, [], True,
                                      min_solution=False,
                                      final_min_solution=True, restart=False, boundary_case=False,
                                      universal_blocking=False, vol_bound=VOL_BOUND,
                                      record_proof=check_proof)
        if isinstance(res, str):
            if to_print:
                print("Not Conflicting")
            else:
                output += "Not Conflicting\n"

        elif res == -1:
            if to_print:
                print("Likely Conflicting")
            else:
                output += "Likely Conflicting\n"

        else:
            conflict_res = True

        if res == 0 and check_proof:
            UNSAT_CORE, derivation = check_and_minimize("proof.txt", "simplified.txt")

            # print("*" * 100)
            print("UNSAT CORE")
            reasons = []
            for r in UNSAT_CORE:
                id = r.id
                if id == 0:
                    adjust_index = i
                elif id > len(rules):
                    continue
                else:
                    adjust_index = id  -1

                conflicting_set.add(adjust_index)

                rule_model = model.ruleBlock.rules[adjust_index]
                # start, end = rule_model._tx_position, rule_model._tx_position_end
                if adjust_index == i:
                    target = rule_model
                    # print("Redundant SLEEC rule:")
                    # print(model_str[start: end])
                    # print("-" * 100)
                else:
                    reasons.append(rule_model)
                    # reasons += (model_str[start: end]) + '\n' + "-" * 100 + '\n'

            local_index = {}

            start, end = target._tx_position, target._tx_position_end
            output += "Conflicting SLEEC rule:\n"
            new_start = len(output)
            local_index[(start, end)] = new_start
            output+= "{}\n".format(model_str[start: end])
            output += ("-" * 100 + '\n')
            output += ("-" * 100 + '\n')
            output += "Because of the following SLEEC rule:\n"
            output += ("-" * 100 + '\n')
            for r in reasons:
                start, end = r._tx_position, r._tx_position_end
                new_start = len(output)
                local_index[(start, end)] = new_start
                output += "{}\n".format(model_str[start: end])
                output += ("-" * 100 + '\n')

            print(output)

            print("TO BE HIGHLIGHTED")
            hls = get_high_light(derivation)
            for s, e in hls:
                s, e = find_relative_pos(s, e, local_index)
                adj_hl.append((s,e))
                print("{} : [{}, {}]".format(output[s: e], s, e))

        clear_all(Actions)
        reset_rules(rules)
        measure_inv.clear()
        derivation_rule.reset()
        print("*" * 100)
        output += "*" * 100 + '\n'
    return conflict_res, output, adj_hl

def check_red(model, rules, Action_Mapping, Actions, model_str="", check_proof=False, to_print= True):
    Measure = Action_Mapping["Measure"]
    measure_inv = forall([Measure, Measure], lambda m1, m2: Implication(EQ(m1.time, m2.time), EQ(m1, m2)))

    output = ""
    adj_hl = []
    red_result = False
    for i in range(len(rules)):
        if to_print:
            print("check rule_{}".format(i + 1))
        else:
            output += "check rule_{}\n".format(i + 1)

        rule = rules[i]
        others = rules[0:i] + rules[i + 1:]
        res = check_property_refining(NOT(rule.get_rule()), set(), [r.get_rule() for r in others] + [measure_inv],
                                      Actions, [], True,
                                      min_solution=False,
                                      final_min_solution=True, restart=False, boundary_case=False,
                                      universal_blocking=False, vol_bound=VOL_BOUND,
                                      record_proof=check_proof)
        if isinstance(res, str):
            if to_print:
                print("Not Redundant")
            else:
                output += "Not Redundant\n"

        elif res == -1:
            if to_print:
                print("Likely Redundant")
            else:
                output += "Likely Redundant\n"

        else:
            red_result = True

        if res == 0 and check_proof:
            UNSAT_CORE, derivation = check_and_minimize("proof.txt", "simplified.txt")

            # print("*" * 100)
            print("UNSAT CORE")
            reasons = []
            for r in UNSAT_CORE:
                id = r.id
                if id == 0:
                    id = i
                elif id <= i:
                    id = id - 1
                else:
                    pass

                if id >= len(rules):
                    continue
                else:
                    adjust_index = id

                rule_model = model.ruleBlock.rules[adjust_index]
                # start, end = rule_model._tx_position, rule_model._tx_position_end
                if adjust_index == i:
                    target = rule_model
                    # print("Redundant SLEEC rule:")
                    # print(model_str[start: end])
                    # print("-" * 100)
                else:
                    reasons.append(rule_model)
                    # reasons += (model_str[start: end]) + '\n' + "-" * 100 + '\n'

            local_index = {}

            start, end = target._tx_position, target._tx_position_end
            output += "Redundant SLEEC rule:\n"
            new_start = len(output)
            local_index[(start, end)] = new_start
            output+= "{}\n".format(model_str[start: end])
            output += ("-" * 100 + '\n')
            output += "Because of the following SLEEC rule:\n"
            output += ("-" * 100 + '\n')
            for r in reasons:
                start, end = r._tx_position, r._tx_position_end
                new_start = len(output)
                local_index[(start, end)] = new_start
                output += "{}\n".format(model_str[start: end])
                output += ("-" * 100 + '\n')

            print(output)

            print("TO BE HIGHLIGHTED")
            hls = get_high_light(derivation)
            for s, e in hls:
                s, e = find_relative_pos(s, e, local_index)
                adj_hl.append((s,e))
                print("{} : [{}, {}]".format(output[s: e], s, e))

        clear_all(Actions)
        reset_rules(rules)
        measure_inv.clear()
        derivation_rule.reset()
        print("*" * 100)
        output += "*" * 100 + '\n'
    return red_result, output, adj_hl


def find_relative_pos( start, end, scopes):
    diff = end - start
    for s, e in scopes.keys():
        if s  <= start <= e:
            # find the index
            diff_s = start - s
            new_s = scopes[(s, e)]
            return new_s+diff_s, new_s+ diff_s+ diff

    return -1, -1





def get_high_light(derivations):
    highlights = []
    for r in derivations:
        if isinstance(r, Fact):
            if r.text_ref:
                highlights.append(r.text_ref)
    return highlights

def reset_rules(rules):
    for r in rules:
        r.get_rule().clear()
        r.get_premise().clear()


def read_model_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()


def parse_sleec(model_file, read_file = True):
    if read_file:
        model_str = read_model_file(model_file)
    else:
        model_str = model_file
    # Parse the model using the metamodel
    model = mm.model_from_str(model_str)
    Action_Mapping = parse_definitions(model.definitions)
    Actions = list(Action_Mapping.values())
    rules = parse_rules(model.ruleBlock, Action_Mapping)
    if model.concernBlock:
        concerns = parse_concerns(model.concernBlock, Action_Mapping)
    else:
        concerns = []

    return model, rules, concerns, Action_Mapping, Actions


# model, rules, Action_Mapping, Actions = parse_sleec("dressingrobot.sleec")
#
# model_str = read_model_file("dressingrobot.sleec")
# check_red(model, rules, Action_Mapping, Actions, check_proof=True, model_str=model_str)

def check_input_red(model_str):
    model, rules, concerns, Action_Mapping, Actions = parse_sleec(model_str, read_file=False)
    res = check_red(model, rules, Action_Mapping, Actions, check_proof=True, model_str=model_str)
    # reset
    scalar_type.clear()
    registered_type.clear()
    text_ref.clear()
    return res


def check_input_conflict(model_str):
    model, rules, concerns, Action_Mapping, Actions = parse_sleec(model_str, read_file=False)
    res = check_conflict(model, rules, Action_Mapping, Actions, check_proof=True, model_str=model_str)
    # reset
    scalar_type.clear()
    registered_type.clear()
    text_ref.clear()
    return res

def check_input_concerns(model_str):
    model, rules, concerns, Action_Mapping, Actions = parse_sleec(model_str, read_file=False)
    res = check_concerns(model, rules, concerns, Action_Mapping, Actions, model_str=model_str)
    # reset
    scalar_type.clear()
    registered_type.clear()
    text_ref.clear()
    return res



# Measure = Action_Mapping["Measure"]
# measure_inv = forall([Measure, Measure], lambda m1, m2: Implication(EQ(m1.time, m2.time), EQ(m1, m2)))
#
# i =4
# print("check R5 red")
# others = rules[0:i] + rules[i+1:]
# res = check_property_refining(NOT(rules[i].get_rule()), set(),[r.get_rule() for r in others] + [measure_inv], Actions, [], True,
#                         min_solution=False,
#                         final_min_solution=True, restart=False, boundary_case=False, universal_blocking=False, record_proof=True)
#
#

# if res == 0:
#     UNSAT_CORE, derivation = check_and_minimize("proof.txt", "simplified.txt")
#     print("*" * 100)
#     print("UNSAT CORE")
#     reasons = ""
#     for r in UNSAT_CORE:
#         id = r.id
#         if id == 0:
#             id = i
#         rule_model = model.ruleBlock.rules[id]
#         start, end = rule_model._tx_position, rule_model._tx_position_end
#         if id == i:
#             print("Redundant SLEEC rule:")
#             print(model_str[start: end])
#             print("-" * 100)
#         else:
#             reasons += (model_str[start: end]) + '\n' + "-" * 100 + '\n'
#
#     print(reasons)
#
#     print("*" * 100)
