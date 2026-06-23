import re
from typing import List, Dict, Set, Optional
from backend.models import ComponentInstance, ConnectionNet, ValidationIssue, PinDefinition, ValidationSummary

HARDWARE_IDEA_TERMS: Set[str] = {
    "actuator",
    "alarm",
    "arduino",
    "audio",
    "battery",
    "bluetooth",
    "button",
    "camera",
    "charger",
    "controller",
    "cube",
    "display",
    "door",
    "enclosure",
    "esp32",
    "fan",
    "gps",
    "haptic",
    "iot",
    "keyboard",
    "knob",
    "lamp",
    "led",
    "light",
    "lock",
    "logger",
    "meter",
    "monitor",
    "module",
    "moisture",
    "motor",
    "mp3",
    "music",
    "nfc",
    "oled",
    "plant",
    "player",
    "printer",
    "pump",
    "reader",
    "relay",
    "remote",
    "rfid",
    "robot",
    "screen",
    "sensor",
    "servo",
    "speaker",
    "station",
    "switch",
    "tag",
    "temperature",
    "thermostat",
    "timer",
    "tracker",
    "usb",
    "wearable",
    "wifi",
    "wristband",
}

HARDWARE_ACTION_TERMS: Set[str] = {
    "alert",
    "alerts",
    "blink",
    "blinks",
    "charge",
    "charges",
    "control",
    "controls",
    "detect",
    "detects",
    "display",
    "displays",
    "heat",
    "lights",
    "log",
    "logs",
    "measure",
    "measures",
    "monitor",
    "monitors",
    "move",
    "moves",
    "notify",
    "notifies",
    "open",
    "opens",
    "play",
    "plays",
    "pump",
    "pumps",
    "rotate",
    "rotates",
    "sense",
    "senses",
    "track",
    "tracks",
    "unlock",
    "unlocks",
    "vibrate",
    "vibrates",
    "water",
    "watering",
    "waters",
}

VAGUE_PROMPT_TERMS: Set[str] = {
    "a",
    "an",
    "and",
    "app",
    "build",
    "cool",
    "create",
    "device",
    "for",
    "hardware",
    "idea",
    "make",
    "me",
    "plan",
    "project",
    "prototype",
    "something",
    "stuff",
    "that",
    "the",
    "thing",
    "to",
    "with",
}


def _tokenize_prompt(prompt: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", prompt.lower())


def _prompt_looks_like_gibberish(prompt: str, tokens: List[str]) -> bool:
    letters = re.sub(r"[^a-z]", "", prompt.lower())
    if len(letters) < 5:
        return False

    has_known_hardware_language = any(token in HARDWARE_IDEA_TERMS or token in HARDWARE_ACTION_TERMS for token in tokens)
    if has_known_hardware_language:
        return False

    vowel_count = len(re.findall(r"[aeiou]", letters))
    vowel_ratio = vowel_count / len(letters)
    long_consonant_run = bool(re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", letters))
    low_variety_placeholder = len(tokens) <= 2 and len(set(letters)) <= 3 and len(letters) >= 5

    return vowel_ratio < 0.16 or long_consonant_run or low_variety_placeholder


def get_generation_input_issue(prompt: str, has_image: bool = False) -> Optional[str]:
    """
    Returns a user-facing reason when the generation input is too vague to compile.
    Image-only generation is valid because the pipeline can infer from the reference.
    """
    prompt_text = (prompt or "").strip()
    if not prompt_text:
        return None if has_image else "Provide a prompt or reference image."

    tokens = _tokenize_prompt(prompt_text)
    if not tokens:
        return "Add a buildable hardware idea before compiling."

    has_hardware_term = any(token in HARDWARE_IDEA_TERMS for token in tokens)
    has_action_term = any(token in HARDWARE_ACTION_TERMS for token in tokens)
    specific_tokens = [token for token in tokens if len(token) >= 3 and token not in VAGUE_PROMPT_TERMS]

    if _prompt_looks_like_gibberish(prompt_text, tokens):
        return "I could not read that as a hardware idea yet. Name a device and what it should do, or clear the text and use an image."

    if len(tokens) < 2 and not has_hardware_term:
        return "Add a little more detail before compiling, like a device plus what it should sense, control, display, or move."

    if not has_hardware_term and not has_action_term and len(specific_tokens) < 3:
        return "Add a concrete hardware idea before compiling, like a device plus what it should sense, control, display, or move."

    if not has_hardware_term and not has_action_term and len(tokens) < 5:
        return "Add what the build should do before compiling."

    return None


def check_safety_violations(prompt: str) -> Optional[str]:
    """
    Checks if the user's prompt contains safety violations that fall outside MVP scope.
    Specifically blocks/warns on: mains AC systems, medical devices, automotive systems, weapons, high-power battery systems.
    """
    prompt_lower = prompt.lower()
    
    # 1. Weapons
    weapon_keywords = ["weapon", "gun", "firearm", "missile", "explosive", "grenade", "bomb", "defense system", "tactical military", "ammunition", "artillery", "pistol"]
    for word in weapon_keywords:
        if word in prompt_lower:
            return f"Safety Block: Weapons-related projects ('{word}') are strictly blocked. Blueprint only supports educational, hobbyist, and safe IoT hardware prototypes."
            
    # 2. Medical Devices
    medical_keywords = ["medical", "pacemaker", "ventilator", "life support", "implant", "clinical health", "surgical", "life-support", "dialysis", "biomedical"]
    for word in medical_keywords:
        if word in prompt_lower:
            return f"Safety Block: Critical medical or life-support devices ('{word}') are strictly blocked. Blueprint only generates low-voltage educational prototypes and does not compile medical grade electronics."

    # 3. Automotive Systems
    automotive_keywords = ["automotive", "car system", "ecu control", "engine control", "vehicle safety", "brake control", "can-bus car", "throttle control", "autopilot car"]
    for word in automotive_keywords:
        if word in prompt_lower:
            return f"Safety Block: High-risk automotive vehicle control systems ('{word}') are blocked to prevent unsafe driving automation prototypes."

    # 4. Mains AC
    mains_keywords = ["mains ac", "110v", "220v", "ac mains", "outlet power", "wall plug ac", "high voltage ac", "240v", "ac outlet", "wall socket"]
    for word in mains_keywords:
        if word in prompt_lower:
            return f"Safety Warning: Projects switching mains AC electricity (110V-240V) are explicitly blocked. Please modify your prompt to use low-voltage DC relays (e.g. switching 5V or 12V DC elements) for electrical safety."

    # 5. High-Power Batteries
    battery_keywords = ["high-power battery", "high power battery", "tesla pack", "48v battery", "60v battery", "high voltage lithium", "ev battery", "electric vehicle battery"]
    for word in battery_keywords:
        if word in prompt_lower:
            return f"Safety Warning: High-power battery packs and electric vehicle charging systems are blocked due to extreme fire and electrical hazards. Please focus on low-voltage battery setups (such as standard 3.7V LiPo or AA cells)."

    return None

def validate_circuit(components: List[ComponentInstance], nets: List[ConnectionNet]) -> List[ValidationIssue]:
    """
    Runs automated electrical and logical validation checks on the structured Hardware IR netlist.
    Returns a list of ValidationIssues (Errors and Warnings) with troubleshooting advice.
    """
    issues: List[ValidationIssue] = []
    
    # Pre-index component pin attributes for fast lookup
    # key: (ref_des, pin_id) -> PinDefinition
    pin_lookup: Dict[tuple, PinDefinition] = {}
    component_lookup: Dict[str, ComponentInstance] = {}
    
    for comp in components:
        component_lookup[comp.ref_des] = comp
        for pin in comp.pins:
            pin_lookup[(comp.ref_des, pin.pin_id)] = pin

    # Pin to Nets reverse lookup to find pin conflict issues
    # key: (ref_des, pin_id) -> List of net_ids
    pin_to_nets: Dict[tuple, List[str]] = {}
    for net in nets:
        for pin_ref in net.pins:
            key = (pin_ref.ref_des, pin_ref.pin_id)
            if key not in pin_to_nets:
                pin_to_nets[key] = []
            pin_to_nets[key].append(net.net_id)

    # ----------------------------------------------------
    # Rule 1: Short Circuit Checker (Power directly to Ground)
    # ----------------------------------------------------
    for net in nets:
        has_power = False
        has_ground = False
        power_pins = []
        ground_pins = []
        
        for pin_ref in net.pins:
            pin = pin_lookup.get((pin_ref.ref_des, pin_ref.pin_id))
            if pin:
                if pin.pin_type.lower() == "power":
                    has_power = True
                    power_pins.append(f"{pin_ref.ref_des}.{pin_ref.pin_id}")
                elif pin.pin_type.lower() == "ground":
                    has_ground = True
                    ground_pins.append(f"{pin_ref.ref_des}.{pin_ref.pin_id}")
                    
        if has_power and has_ground:
            issues.append(ValidationIssue(
                severity="CRITICAL",
                category="Short Circuit",
                description=f"Direct electrical short detected in net '{net.name}' ({net.net_id}). "
                            f"Power pins [{', '.join(power_pins)}] are connected directly to Ground pins [{', '.join(ground_pins)}].",
                troubleshooting="Separate the power rail connections from the ground reference rail. Power pins must only connect to other power nodes, never directly to GND."
            ))

    # ----------------------------------------------------
    # Rule 2: Voltage Mismatch Checker
    # ----------------------------------------------------
    for net in nets:
        voltages: Set[float] = set()
        connected_pins = []
        
        for pin_ref in net.pins:
            pin = pin_lookup.get((pin_ref.ref_des, pin_ref.pin_id))
            if pin and pin.voltage is not None:
                # Store pin name and operating voltage
                voltages.add(pin.voltage)
                connected_pins.append(f"{pin_ref.ref_des}.{pin_ref.pin_id} ({pin.voltage}V)")
                
        # If we have multiple different positive voltages on the same signal rail
        if len(voltages) > 1:
            max_v = max(voltages)
            min_v = min(voltages)
            # If the difference is significant (e.g. 5.0V and 3.3V on the same net)
            if max_v - min_v > 0.5:
                issues.append(ValidationIssue(
                    severity="WARNING",
                    category="Voltage Mismatch",
                    description=f"Potential voltage mismatch in net '{net.name}' ({net.net_id}). "
                                f"Pins with different voltages are connected on the same net: {', '.join(connected_pins)}.",
                    troubleshooting=f"Use an active level-shifter (e.g., TXB0104) to bridge logic between {min_v}V and {max_v}V lines, or use a component operating at compatible voltages."
                ))

    # ----------------------------------------------------
    # Rule 3: Floating / Unpowered IC Check
    # ----------------------------------------------------
    # Identify which components are active ICs (MCUs, Sensors, Actuators, Displays)
    for ref_des, comp in component_lookup.items():
        if comp.category.lower() in ["microcontroller", "sensor", "display", "actuator"]:
            # Check if this component has power & ground pins and if they are connected
            has_power_pin = False
            has_ground_pin = False
            power_connected = False
            ground_connected = False
            
            p_pin_ids = []
            g_pin_ids = []
            
            for pin in comp.pins:
                if pin.pin_type.lower() == "power":
                    has_power_pin = True
                    p_pin_ids.append(pin.pin_id)
                    # Check if this specific pin is in any net
                    if (ref_des, pin.pin_id) in pin_to_nets:
                        power_connected = True
                elif pin.pin_type.lower() == "ground":
                    has_ground_pin = True
                    g_pin_ids.append(pin.pin_id)
                    if (ref_des, pin.pin_id) in pin_to_nets:
                        ground_connected = True
                        
            # If it has pins but they're not connected
            if has_power_pin and not power_connected:
                issues.append(ValidationIssue(
                    severity="CRITICAL",
                    category="Unpowered IC",
                    description=f"Active component '{comp.name}' ({ref_des}) is unpowered. "
                                f"None of its power pins [{', '.join(p_pin_ids)}] are connected to an active power net.",
                    troubleshooting=f"Connect one of the VCC/Power pins on {ref_des} to the main power rail (e.g., 3.3V or 5V net)."
                ))
            if has_ground_pin and not ground_connected:
                issues.append(ValidationIssue(
                    severity="CRITICAL",
                    category="Unpowered IC",
                    description=f"Active component '{comp.name}' ({ref_des}) has no ground reference. "
                                f"None of its ground pins [{', '.join(g_pin_ids)}] are tied to the GND net.",
                    troubleshooting=f"Connect the GND/Ground pin on {ref_des} to the common system Ground net (GND)."
                ))

    # ----------------------------------------------------
    # Rule 4: Pin Reuse Conflict
    # ----------------------------------------------------
    for (ref_des, pin_id), net_ids in pin_to_nets.items():
        # Exclude passive/power/ground buses which naturally share pins
        pin = pin_lookup.get((ref_des, pin_id))
        if pin and pin.pin_type.lower() not in ["power", "ground", "passive"]:
            if len(net_ids) > 1:
                comp = component_lookup.get(ref_des)
                comp_name = comp.name if comp else ref_des
                issues.append(ValidationIssue(
                    severity="CRITICAL",
                    category="Pin Conflict",
                    description=f"Pin reuse conflict detected! Pin '{pin_id}' on '{comp_name}' ({ref_des}) "
                                f"is connected to multiple independent signal nets: {', '.join(net_ids)}.",
                    troubleshooting=f"Reassign pin '{pin_id}' to only belong to a single signal net. Signal pins cannot be shared directly across separate signal/communication lines."
                ))

    # ----------------------------------------------------
    # Rule 5: Over-Current Warn Check (Power-Hungry Actuators)
    # ----------------------------------------------------
    has_mcu = False
    mcu_ref = None
    high_draw_actuator_refs: Dict[str, str] = {}
    
    for ref_des, comp in component_lookup.items():
        if comp.category.lower() == "microcontroller":
            has_mcu = True
            mcu_ref = ref_des
        else:
            component_text = f"{comp.name} {comp.part_number}".lower()
            is_high_draw_actuator = (
                comp.part_number in ["Relay-5V-1Ch", "SG90-Servo"]
                or any(keyword in component_text for keyword in ["relay", "servo", "motor", "pump"])
            )
            if is_high_draw_actuator:
                high_draw_actuator_refs[ref_des] = f"{comp.name} ({ref_des})"
            
    if has_mcu and high_draw_actuator_refs:
        for net in nets:
            if net.net_type.lower() != "power" or net.voltage != 3.3:
                continue

            contains_mcu_power_pin = False
            powered_actuators = []
            for pin_ref in net.pins:
                pin = pin_lookup.get((pin_ref.ref_des, pin_ref.pin_id))
                if not pin or pin.pin_type.lower() != "power":
                    continue
                if pin_ref.ref_des == mcu_ref:
                    contains_mcu_power_pin = True
                elif pin_ref.ref_des in high_draw_actuator_refs:
                    powered_actuators.append(high_draw_actuator_refs[pin_ref.ref_des])
            
            if contains_mcu_power_pin and powered_actuators:
                issues.append(ValidationIssue(
                    severity="WARNING",
                    category="Overcurrent Risk",
                    description=f"High-power actuator(s) [{', '.join(powered_actuators)}] are powered from the same 3.3V low-current output "
                                f"net '{net.name}' as the MCU ({mcu_ref}). Relays and servo motors draw peak currents that can crash the microcontroller or burn out its internal voltage regulator.",
                    troubleshooting="Isolate the actuator power. Connect the servo/relay power pin to a dedicated 5V input rail or external power source, sharing only the ground reference (GND) with the MCU."
                ))

    return issues

def build_validation_summary(issues: List[ValidationIssue]) -> ValidationSummary:
    """
    Groups a list of individual ValidationIssue models into critical, warning, and info lists.
    """
    critical = [issue for issue in issues if issue.severity.upper() == "CRITICAL"]
    warning = [issue for issue in issues if issue.severity.upper() == "WARNING"]
    info = [issue for issue in issues if issue.severity.upper() == "INFO"]
    return ValidationSummary(critical=critical, warning=warning, info=info)
