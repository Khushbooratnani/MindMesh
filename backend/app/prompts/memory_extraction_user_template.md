Extract memory information from the following input.

Media type:
{media_type}

Content:
{content}

Return JSON using exactly this structure:

{
  "description": "string",
  "summary": "string",
  "entities": {
    "people": [],
    "places": [],
    "locations": [],
    "events": [],
    "organizations": []
  },
  "semantics": {
    "topics": [],
    "activities": [],
    "sentiment": "positive | neutral | negative | mixed | unknown",
    "mood": []
  },
  "temporal": {
    "mentioned_dates": [],
    "inferred_time": null,
    "time_of_day": "morning | afternoon | evening | night | unknown | null"
  },
  "additional_attributes": [
    {
      "key": "string",
      "value": "string | number | boolean | object | array",
      "confidence": 0.0,
      "source": "llm"
    }
  ]
}
