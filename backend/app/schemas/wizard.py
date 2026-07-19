from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional, List, Tuple, Any, Union

from .entity import CharacterCard as CharacterCard  # Replace simplified model with full character card
from .entity import SceneCard as SceneCard
from .entity import OrganizationCard as OrganizationCard
from .entity import EntityType as EntityType


class Text(BaseModel):
    '''
    General text model, freely stores various content
    '''
    content: str = Field(description="Any text content, should use/convert to markdown format text")

# --- Schemas for Tags ---

class Tags(BaseModel):
    """
    Unified tag model.
    """
    theme: str = Field(default="", description="Theme category, format: major-sub")
    audience: Literal['General','Male', 'Female'] = Field(default='General', description="Target audience")
    narrative_person: Literal['First Person', 'Third Person'] = Field(default='Third Person', description="Narrative person (first person/third person)")
    story_tags: List[Tuple[str, Literal['Low', 'Medium', 'High']]] = Field(default=[], description="Category tags and weight tier (low/medium/high)")
    affection: str = Field(default="", description="Affection / relationship tag")


class SpecialAbility(BaseModel):
    name: str = Field(description="Special ability name")
    description: str = Field(description="Specific description of the special ability")


class SpecialAbilityResponse(BaseModel):
    """0: Request model for designing special abilities based on tags"""
    special_abilities_thinking: str = Field(description="Creation thinking process from tags to special abilities.",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: based on the tags 'Rebirth' and 'Invincible Flow', I need to design a special ability that allows the protagonist to keep trying, keep getting stronger, and ultimately reach an invincible state. A single rebirth is not enough to support the long-term development of 'Invincible Flow', so I deepen the 'Rebirth' trait into an 'infinite resurrection with time regression' ability, where each resurrection retains experience and memory; this both fits the 'Rebirth' characteristic and provides logical support for the protagonist's path to 'invincibility'. Meanwhile, combined with the 'Otherworld Continent' and 'Civilization Deduction' background, this ability lets the protagonist accumulate knowledge and experience through repeated trial and error when facing an unknown world, thereby achieving dimensional suppression and rising rapidly. This special ability setting makes readers strongly anticipate how the protagonist uses this ability to solve dilemmas and overturn the old order."])
    special_abilities: Optional[List[SpecialAbility]] = Field(None, description="Main special ability info. A special ability can be concrete things like various systems, simulators, etc., or some advantage / talent / constitution, etc.; for example, if the protagonist is reborn or transmigrates, then their foresight is also a special ability.")


class OneSentence(BaseModel):
    """1: Request model for designing a one-sentence summary based on tags and special abilities"""
    one_sentence_thinking: str = Field(description="Creation thinking process from tags / special ability to one-sentence summary.",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: considering the theme of 'Fantasy - Otherworld Continent' and tags such as 'Transmigration' and 'Otherworld Science Flow', I first need to build a cross-world story framework. The encounter between a modern kendo master and an otherworld magician is a good entry point, and the 'Forbidden Magic Portal' special ability provides a reasonable opportunity for this encounter. Meanwhile, the 'Single CP' affection tag requires this relationship to become an important thread of the story. The 'Civilization Collision' and 'Otherworld Science Flow' tags suggest letting the protagonist bring the knowledge advantage of the modern world, forming unique conflicts and highlights. Combining these elements, I decide to build a story about a modern person entering a magic world and influencing the fate of the entire otherworld through knowledge advantage and personal growth."])
    one_sentence: str = Field(description="One sentence summarizing the entire novel content")


class ParagraphOverview(BaseModel):
    """2: Request model for expanding into a paragraph overview based on one-sentence summary etc."""
    overview_thinking: str = Field(description="Creation thinking process from one-sentence summary to a paragraph outline.",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: based on the one-sentence summary, further think about the specific unfolding of the story. Starting from the 'Transmigration' tag, I need to explain the protagonist's identity change and initial dilemma after transmigrating. 'Villain Flow' and 'Behind-the-Scenes Flow' determine that the protagonist must adopt unconventional villainous means. 'Farming Flow' suggests detailing the development process of the demon society. The 'Arrogant Talent' special ability provides the protagonist's unique way of solving problems. The whole story needs to show how the protagonist uses modern thinking and strategy to complete the demon clan transformation and the peaceful infiltration of the human world within a limited time."])
    overview: str = Field(description="Expanded novel outline")


class SocialSystem(BaseModel):
    power_structure: str = Field(description="Power structure (e.g.: feudal dynasty / capitalist federation)")
    currency_system: List[str] = Field(description="Currency system")
    background:List[str]=Field(description="The power landscape background, historical legends, etc. of this social system")
    major_power_camps: List[OrganizationCard] = Field(description="Main organizations / sects / faction camps; only generate core organizations with cross-volume long-term impact here.")
    civilization_level: Optional[str] = Field(description="Technology / civilization development level")

class CoreSystem(BaseModel):
    system_type: str = Field(min_length=1,description="System type (power / society / technology / ability, etc.)")
    name: str = Field(description="System name (e.g.: fighting spirit / capital rules / court intrigue)")
    levels: Optional[List[str]] = Field(None, description="Level / class division (optional)")
    source: str = Field(description="Energy / power source (e.g.: spiritual energy / capital / imperial power)")

class SettingItem(BaseModel):
    title: str = Field(description="Setting title, e.g.: geographic cosmology, historical legends, racial settings, etc.")
    description: str = Field(description="Specific description of this setting")

class WorldviewTemplate(BaseModel):
    """
    Worldview template
    """
    world_name: str = Field(min_length=2, description="World name")
    core_conflict: str = Field(description="World core conflict (e.g.: resource competition / racial hatred)")
    social_system: SocialSystem = Field(description="Social system")
    power_systems: List[CoreSystem] = Field(description="Core system list, can include multiple systems such as power / technology / ability; avoid overly complex settings, set at most two systems. If it is a realistic subject such as reality / history, it can be left empty",max_length=2)
    # key_settings: Optional[List[SettingItem]] = Field(description="Other key worldview settings (optional)")

class WorldBuilding(BaseModel):
    world_view_thinking: str = Field(description="Worldview design thinking process",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: when designing the worldview, I hope to build a framework that is both close to reality and full of sci-fi imagination. First, to give readers a sense of immersion, I choose to set the story background in a modern city, so that the conflict between the protagonist's special ability and daily life is more tense. But a modern city alone is obviously not enough to support the 'Space-Time Travel' theme, so I introduce 'Dreams' as a bridge connecting reality and the future. This dream world is initially a reflection of reality, but with the protagonist's intervention, it will undergo drastic changes, even showing differences in the future world such as 'Old Sea' and 'New Sea City', which adds layers and exploration space to the worldview. To explain these changes, I need a rigorous set of space-time laws, such as 'Space-Time Butterfly Effect' and 'History Line Correction'; these laws not only explain the interaction between dreams and reality, but also provide a logical basis for plot advancement and conflict generation. Meanwhile, to carry the 'Civilization Deduction' and 'Otherworld Science Flow' tags, I conceive a hidden organization behind the scenes that masters technology beyond the era and a deep understanding of space-time laws; their existence embodies the world's core contradiction — namely the control over the direction of history. In terms of social systems, the real world is a modern society, while the future dream may present multiple faces of highly developed technology but distorted society (such as credits above all) or apocalyptic wasteland (such as radiation disasters); this contrast can enhance the depth and cautionary meaning of the story. In terms of the core driving system, in addition to the protagonist's dream ability, scientific concepts such as 'Space-Time Particles' are needed as the power source and theoretical support, making the entire worldview self-consistent and full of exploration potential under the sci-fi framework."])
    world_view: WorldviewTemplate


# === Step 3: Blueprint Schemas ===


class Blueprint(BaseModel):
    volume_count: int = Field(description="Expected number of volumes for the novel, usually set to 3~6 volumes")
    character_thinking: str = Field(description="Character design thinking process",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: when designing characters, I adhere to the principle of 'diversity and complementarity', ensuring that each core character plays a unique role in the story and forms a close connection with the protagonist's group.\n\nFirst is the protagonist Wang Xiaoming. As a 'transmigrator', he must possess modern thinking and adaptability. I set him as a kendo master, which both lets him quickly integrate into the otherworld and echoes the otherworld's 'kendo' system. His core drives are 'high reward' and 'protecting Haiwen', which gradually transforms him from a bystander into a participant and guardian of the otherworld. His growth arc will be 'from an ordinary person in the real world to the savior of the otherworld', closely tied to the 'Evolution Flow' tag.\n\nThe heroine Haiwen is the guide of the story. She must be a core figure of the otherworld, with powerful magic talent and a unique background. I set her as a 'genius magician' and 'a fugitive from a royal marriage', which provides her with her initial dilemma and motivation. The 'flash marriage' setting with the protagonist quickly establishes their CP relationship and lays the foundation for subsequent emotional development. Her core drives are 'escaping the marriage' and 'saving the world', which lets her find a balance between personal fate and the world's fate. Her character arc is 'from a fugitive to a royal palace magician who saves the world', showing her growth and responsibility.\n\nXisi, as the main antagonist, must be powerful and mysterious. I set her as 'Haiwen's aunt' and an 'evil magician'; this kinship adds complexity and emotional tension to the story. Her core motive is 'destroying the world', closely related to the curse of the lost civilization. Her character arc is 'from a genius magician to a destroyer who ultimately chooses to leave', adding a tragic tone to the story's ending.\n\nLin Xiaoxue serves as the bridge connecting the real world; her 'top student' setting lets her provide modern knowledge to the otherworld, embodying the 'Otherworld Science Flow' and 'Civilization Collision' tags.\n\nThrough the design of these characters, I hope to build a group of characters full of tension, emotionally rich, and able to jointly drive the grand narrative."])
    character_cards: List[CharacterCard] = Field(description="Core character card list, only generate core characters with cross-volume long-term impact here")

    # organization_thinking:str=Field(description="Organization / faction / camp design thinking process, note the distinction from scene")
    # organization_cards: List[OrganizationCard] = Field(description="Core organization / faction / camp card list, only generate core organizations with cross-volume long-term impact here. Note the distinction from scene_cards")

    scene_thinking: str = Field(description="Scene design thinking process",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: when designing maps and scenes, I follow the principle of going from local to global, from known to unknown, layer by layer, to ensure the rhythm of the story and the gradual unfolding of the worldview. My core idea is: each scene is not only the place where the story happens, but also the key to advancing the plot, showing character growth, and revealing worldview secrets.\n\n**Volume 1: Entering the Otherworld and Initial Exploration**\nI first set Blue Star (the real world) as the starting point of the story and the protagonist's 'known world', giving readers a sense of immersion. Then through 'Molanta' and 'Lante Kingdom (Bright Moon City)' I introduce the core region of the otherworld, a typical scene where magic and sword coexist, and also the eruption point of early conflicts. Molanta, as the holy land of magicians, is both Haiwen's background and the place where the protagonist learns magic. Bright Moon City represents the political center and war front of the otherworld. The role of these scenes is to let the protagonist initially adapt to the otherworld, show his adaptability and initial strength improvement, and introduce the main forces.\n\n**Volume 2: Power Development and Alliance Building**\nAs the plot develops, I need a broader stage to show the protagonist group's power expansion and grand plans. Therefore, I introduce 'Lante Kingdom (Jinghong City)' as the new ally base, which will become the strategic center for the princess's restoration and alliance building. Meanwhile, to show the comprehensiveness of the war, I design 'Gaolan Federation (Linya City / Central Watchtower / Sunrise Mountain)' as an important battlefield and political arena, and use the conflicts here to drive the formation of the alliance. The liberation of 'Bright Moon City' is the climax of this volume, marking a key step in the restoration plan. The role of these scenes is to let the protagonist group shift from passive defense to active attack, show their strategic vision and leadership, and facilitate the establishment of the alliance.\n\n**Volume 3: War of Unification and the Revelation of Ancient Secrets**\nEntering the third volume, the story focus shifts to unifying the otherworld continent and revealing deeper secrets. Therefore, I extend the scenes to 'Sun-Moon Kingdom' and 'Saint Valen Empire (Tesistinburg)'. The Sun-Moon Kingdom is the necessary path for the allied forces' advance, and the battles here show the protagonist group's powerful strength. The capital of the Saint Valen Empire, 'Tesistinburg', is the location of the final battle, and its fall marks the end of the old order. The role of these scenes is to complete the great cause of unification, while revealing the deep secrets of the worldview, foreshadowing the final crisis.\n\n**Volume 4: Doomsday Crisis and the Final Choice**\nIn the last volume, the world faces destruction, and the scene design revolves around 'salvation' and 'ending'. 'Linya City' and 'Jinghong City' appear again, but this time they carry the hope of collecting royal blood and seeking survival through technology. The final 'Origin Land / Burning Peak' is the stage of the decisive battle, the source of the curse and the key to lifting it. The role of these scenes is to gather all clues, complete the final redemption, and let the protagonist group make the final choice about belonging, bringing the whole story to a close."])
    scene_cards: List[SceneCard] = Field(description="Main map / scene / dungeon card list, only generate core maps / scenes with cross-volume long-term impact here. Note the connection with organization_cards; for example, if a map is the activity range of an organization / faction, it should be marked.")


# === Step 4: Volume Outline Schemas===

class CharacterAction(BaseModel):
    """Character card, covering various info"""
    name: str = Field(description="Character name")
    description: str = Field(description="Describe this character's main deeds in this volume from the first-person perspective")

class StoryLine(BaseModel):
    """Storyline info"""
    story_type: Literal['Main', 'Side'] = Field(description="Storyline type")
    name: str = Field(description="Represent this line with a simple name")
    overview: str = Field(description="Storyline content overview, should be appropriately detailed; all scenes, characters and other elements involved should be reflected in this overview.")


class VolumeOutline(BaseModel):
    """
    Core data model of the volume outline
    """
    volume_number: Optional[int] = Field(description="Which volume")
    thinking: Optional[str] = Field(description="Based on the provided worldview, characters, maps / dungeons, think about how to unfold this volume; what main / side lines need to be designed? How to advance the plot?",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: as the opening volume, my core thinking is how to quickly establish the protagonist's 'infinite resurrection' special ability characteristic, and combine it with the cruel otherworld continent background to create a strong sense of survival oppression, thereby driving the protagonist to rise from despair. I need to design a progressive growth path that lets the protagonist, from a dying person, accumulate experience and knowledge through each resurrection, gradually adapt to the environment, and finally gain a foothold in City A, accumulate initial capital, and establish initial power. Meanwhile, for the subsequent grand narrative, I must foreshadow the worldview in this volume, such as the solidification of social classes and the manipulation of higher civilizations, gradually revealed through the protagonist's perspective. In terms of character shaping, I will introduce a group of partners with distinct personalities, who are both the protagonist's help and can contrast the protagonist's strength and specialness through their perspectives. In terms of exciting points, the protagonist uses the 'foresight' advantage of the special ability to achieve dimensional suppression in the stock market and adventures, as well as the final revenge against the early antagonist, all of which will be important exciting-point designs."])
    main_target: StoryLine = Field(description="Based on thinking, design the main-line goal; what level should the protagonist develop to? Accurate data needed")
    branch_line: Optional[List[StoryLine]] = Field(description="The side lines or branch lines of this volume, containing 1~3 core side lines")
    character_thinking: Optional[str] = Field(description="Combine overview and provided character info, such as personality, core drive, character arc, etc., and think about what to drive the character entities to do in this volume? Which characters should appear? Should auxiliary characters be introduced?",examples=["Example output, only for learning the thinking approach, do not be influenced by the specific content: in this volume, I will focus on driving the protagonist, letting him make full use of the 'infinite resurrection' ability to gradually grow from a survivor in despair into the leader of City A. He will learn combat skills and social rules through repeated trial and error, and use information asymmetry to quickly accumulate wealth in the stock market. I also need to introduce core supporting characters such as Sun Qingyu, Wang Huo, and Han Tian, letting them play important auxiliary roles in the protagonist's growth process: Sun Qingyu, as the protagonist's first partner and loyal follower, will witness and participate in the protagonist's early rise; Wang Huo provides technical support and becomes the confidant of the protagonist's 'resurrection' secret; Han Tian provides key help in equipment modification and technology R&D. The appearance and interaction of these characters can not only drive the plot, but also enrich the protagonist's characterization, showing his outstanding strategy and resourcefulness. Meanwhile, Lin Sen, as the main antagonist of this volume, will be the concrete target of the protagonist's early resistance against the old order; his existence will constantly stimulate the protagonist to become stronger and seek revenge."])
    new_character_cards: Optional[List[CharacterCard]] = Field(default=None, description="If there are new key characters, supplement their info here, life_span is Short Term. Avoid introducing new characters unless necessary")
    new_scene_cards: Optional[List[SceneCard]]= Field(default=None, description="If there are new key scenes / maps / dungeons, supplement their info here, life_span is Short Term. Avoid introducing new scenes unless necessary")
    # stage_lines: Optional[List[StageLine]] = Field(default=[], description="Design the detailed story thread of this volume, divided by stages; note that when splitting story stages, the detail should be appropriate, and the chapter span of each stage should not be too large, preferably no more than 30 chapters")
    stage_count:int=Field(description="Expected stage plot of this volume; divide the volume's plot into n stages, usually 4~6")
    character_action_list: Optional[List[CharacterAction]] = Field( description="Based on the in-volume design, summarize the actions and changes of key character entities")
    entity_snapshot: Optional[List[str]] = Field(description="At the end of the volume, snapshot state info of key entities (mainly characters), including level / cultivation realm, wealth, techniques and other accurate info, to converge the plot")

class WritingGuide(BaseModel):
    """
    Writing guide, used to guide the AI on details to note when creating in a specific volume.
    """
    volume_number: int = Field(description="The volume number this writing guide corresponds to")
    content: str = Field(description="Specific content generated by the AI based on methodology, used to guide the writing of this volume. Word count controlled within 1000 words.",min_length=100)


class ReviewResultCardContent(BaseModel):
    review_target_card_id: int = Field(description="Reviewed card ID")
    review_target_title: str = Field(description="Reviewed card title")
    review_target_type: Literal['card'] = Field(default='card', description="Reviewed target type")
    review_type: Literal['chapter', 'stage', 'card', 'custom'] = Field(description="Review type")
    review_profile: str = Field(description="Review profile code")
    review_target_field: Optional[str] = Field(default=None, description="Reviewed field path")
    quality_gate: Literal['pass', 'revise', 'block'] = Field(description="Review conclusion")
    review_markdown: str = Field(description="Review result body, in markdown format")
    prompt_name: str = Field(description="Name of the prompt used for the review")
    llm_config_id: Optional[int] = Field(default=None, description="Model config used for the review")
    reviewed_at: str = Field(description="Review time (ISO string)")
    target_snapshot: Optional[str] = Field(default=None, description="Snapshot of reviewed content")
    meta: Optional[dict[str, Any]] = Field(default_factory=dict, description="Extended metadata")

class ChapterOutline(BaseModel):
    """Chapter outline"""
    volume_number: int = Field(description="Volume number; if not found, set to 0")
    stage_number:int=Field(description="Which stage this chapter belongs to, starting from 1")
    title: str= Field(description="Chapter title")
    chapter_number: int = Field(description="Chapter number")

    overview: str = Field(description="Chapter detailed outline, appropriately detailed, avoid being too thin. If the protagonist has significant improvement, the related info cannot be omitted and must be described with accurate data (such as a major strength improvement, or how much economy or resources grew).",min_length=100)
    entity_list: List[str] = Field(
        description="List of important entities appearing in the chapter; can only be selected from the organization / character / scene card entities provided in the context, and must not be added or invented; entity names must be pure names (no parentheses / remarks). Note: to streamline the context, avoid redundant entities in the entity list that do not appear in this chapter",
    )



class StageLine(BaseModel):
    """Story info divided by stages"""
    volume_number:int=Field(description="Which volume this story stage belongs to")
    stage_number:int=Field(description="Which stage this story stage is, starting from 1")
    stage_name: str = Field(description="Briefly summarize this stage with a name or one sentence")
    reference_chapter: Tuple[int, int] = Field(description="The start and end chapter numbers of this part of the plot, the span is usually about 10~20 chapters")
    analysis: Optional[str] = Field(description="From the first-person perspective of an experienced web novel writer as the author, how does 'I' think about setting up this part of the plot; what role does this part of the plot play for the volume's main / side lines? What are the exciting points of this stage's plot? Is a hook / suspense set at the end?")
    overview: Optional[str] = Field(description="Specific overview of this stage's plot content, should be appropriately detailed; the main entities involved, such as characters, scenes / maps, organizations and other elements, should be reflected in this overview. In addition, if the protagonist has significant improvement (such as how much the protagonist's strength or status improved, or how much the protagonist's wealth or resources grew), the related info must be described with accurate data and cannot be omitted")
    chapter_outline_list:Optional[List[ChapterOutline]]=Field(description="Generate the required chapter outlines based on reference_chapter and overview. Note that the title of the chapter outline should not contain prefixes such as 'Chapter x'")
    entity_snapshot: Optional[List[str]] = Field(description="At the end of the stage, snapshot state info of key entities (mainly characters), including level / cultivation realm, wealth, techniques and other accurate info, to converge the plot, ensuring that by the last stage, the plot development can converge the entity state to the entity state at the end of the volume.")
    @model_validator(mode="after")
    def validate_chapter_outline_coverage(self):
        # Allow empty list for workflow post-processing cleanup.
        if not self.chapter_outline_list:
            return self

        start, end = self.reference_chapter
        if start > end:
            raise ValueError("reference_chapter start must be <= end")

        actual_numbers = [item.chapter_number for item in self.chapter_outline_list]
        expected_numbers = list(range(start, end + 1))
        if actual_numbers != expected_numbers:
            raise ValueError(
                "chapter_outline_list.chapter_number must be contiguous and fully cover reference_chapter"
            )
        return self


# === Step 6: Batch Chapter Outline Schemas===

class Chapter(BaseModel):
    volume_number: int = Field( description="Volume number; if not found, set to 0")
    stage_number: int=Field(description="Which stage this chapter belongs to, starting from 1")
    title: str = Field(description="Chapter title")
    chapter_number: int = Field(description="Chapter number")

    entity_list: List[str] = Field(
        description="List of important entities participating in the chapter; can only be selected from the provided entities; name must be a pure name (no parentheses / remarks)",
    )
    content:Optional[str]=Field(default="",description="Chapter body content")

