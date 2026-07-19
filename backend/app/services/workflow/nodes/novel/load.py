from typing import Any, Dict, List, Optional, AsyncIterator
import os
import re
from loguru import logger
from pydantic import Field, BaseModel

from ...registry import register_node
from ..base import BaseNode


class NovelLoadInput(BaseModel):
    """Novel.Load node input - all parameters here"""
    root_path: str = Field(
        ..., 
        description="Novel root directory path",
        json_schema_extra={"x-component": "DirectorySelect"}
    )
    file_pattern: str = Field(
        r".*\.(txt|md)$", 
        description="Filename matching regex"
    )
    volume_pattern: str = Field(
        r"第[一二三四五六七八九十0-9]+[卷部纪]", 
        description="Volume folder matching regex"
    )
    chapter_pattern: str = Field(
        r"第([零一二三四五六七八九十百千0-9]+)章", 
        description="Chapter name matching regex (used to extract the index)"
    )


class NovelLoadOutput(BaseModel):
    """Novel.Load node output"""
    chapter_list: List[Dict[str, Any]] = Field(..., description="Chapter metadata list")
    volume_list: List[str] = Field(..., description="Volume list")


@register_node
class NovelLoadNode(BaseNode[NovelLoadInput, NovelLoadOutput]):
    node_type = "Novel.Load"
    category = "novel"
    label = "Load Novel"
    description = "Scan the novel directory and generate chapter list metadata"
    
    input_model = NovelLoadInput
    output_model = NovelLoadOutput

    async def execute(self, inputs: NovelLoadInput) -> AsyncIterator[NovelLoadOutput]:
        """Execute novel loading"""
        # Validate that the directory exists
        if not os.path.exists(inputs.root_path):
            raise ValueError(f"Directory does not exist: {inputs.root_path}")
            
        chapter_list = []
        volumes = set()
        
        # Compile regexes
        try:
            file_re = re.compile(inputs.file_pattern)
            vol_re = re.compile(inputs.volume_pattern)
            chap_re = re.compile(inputs.chapter_pattern)
        except Exception as e:
            raise ValueError(f"Regex compilation failed: {e}")

        logger.info(f"[Novel.Load] Starting scan: {inputs.root_path}")
        
        # Traverse the directory
        for dirpath, dirnames, filenames in os.walk(inputs.root_path):
            # Determine the current volume
            rel_path = os.path.relpath(dirpath, inputs.root_path)
            current_volume = "Default Volume"
            
            if rel_path != ".":
                parts = rel_path.split(os.sep)
                if parts:
                    potential_vol = parts[0]
                    if vol_re.search(potential_vol):
                        current_volume = potential_vol
                    else:
                        current_volume = potential_vol

            volumes.add(current_volume)
            
            for fname in filenames:
                if not file_re.match(fname):
                    continue
                    
                full_path = os.path.join(dirpath, fname)
                title = os.path.splitext(fname)[0]
                
                # Try to extract the chapter index
                idx = 0
                match = chap_re.search(title)
                if match:
                    if match.groups():
                        try:
                            idx = int(match.group(1))
                        except ValueError:
                            pass
                    else:
                        num_match = re.search(r"\d+", match.group())
                        if num_match:
                            idx = int(num_match.group())
                
                # Build metadata
                meta = {
                    "title": title,
                    "path": full_path,
                    "volume": current_volume,
                    "index": idx,
                    "filename": fname
                }
                chapter_list.append(meta)

        # Sort
        chapter_list.sort(key=lambda x: (x['volume'], x['index'], x['title']))
        
        # Extract the volume list and natural-sort it
        volumes_set = set(item['volume'] for item in chapter_list)
        
        # Natural sort function
        def natural_sort_key(text):
            """Convert text to a sortable key, supporting Chinese numerals and Arabic numerals"""
            import re
            
            # Chinese numeral map
            chinese_num_map = {
                '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
                '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                '百': 100, '千': 1000
            }
            
            def chinese_to_num(s):
                """Simple Chinese numeral conversion (supports one to ninety-nine)"""
                if not s:
                    return 0
                if s in chinese_num_map:
                    return chinese_num_map[s]
                # Handle "十X" or "X十" or "X十X" (ten-X / X-ten / X-ten-X)
                if '十' in s:
                    parts = s.split('十')
                    if len(parts) == 2:
                        left = chinese_num_map.get(parts[0], 1 if not parts[0] else 0)
                        right = chinese_num_map.get(parts[1], 0)
                        return left * 10 + right
                return 0
            
            # Extract the numeric part
            match = re.search(r'第([一二三四五六七八九十百千0-9]+)[卷部纪]', text)
            if match:
                num_str = match.group(1)
                # Try Arabic numerals
                if num_str.isdigit():
                    return int(num_str)
                # Try Chinese numerals
                return chinese_to_num(num_str)
            return 0
        
        volumes = sorted(list(volumes_set), key=natural_sort_key)
        
        logger.info(f"[Novel.Load] Scan completed, found {len(chapter_list)} chapters, {len(volumes)} volumes")
        
        # Return the typed output directly
        yield NovelLoadOutput(
            chapter_list=chapter_list,
            volume_list=volumes
        )