CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
FOR (m:Memory)
REQUIRE m.memory_id IS UNIQUE;

CREATE CONSTRAINT person_normalized_name_unique IF NOT EXISTS
FOR (p:Person)
REQUIRE p.normalized_name IS UNIQUE;

CREATE CONSTRAINT place_normalized_name_unique IF NOT EXISTS
FOR (p:Place)
REQUIRE p.normalized_name IS UNIQUE;

CREATE CONSTRAINT location_normalized_name_unique IF NOT EXISTS
FOR (l:Location)
REQUIRE l.normalized_name IS UNIQUE;

CREATE CONSTRAINT event_normalized_name_unique IF NOT EXISTS
FOR (e:Event)
REQUIRE e.normalized_name IS UNIQUE;

CREATE CONSTRAINT organization_normalized_name_unique IF NOT EXISTS
FOR (o:Organization)
REQUIRE o.normalized_name IS UNIQUE;

CREATE CONSTRAINT topic_normalized_name_unique IF NOT EXISTS
FOR (t:Topic)
REQUIRE t.normalized_name IS UNIQUE;

CREATE CONSTRAINT activity_normalized_name_unique IF NOT EXISTS
FOR (a:Activity)
REQUIRE a.normalized_name IS UNIQUE;

CREATE CONSTRAINT mood_normalized_name_unique IF NOT EXISTS
FOR (m:Mood)
REQUIRE m.normalized_name IS UNIQUE;

CREATE CONSTRAINT food_drink_normalized_name_unique IF NOT EXISTS
FOR (f:FoodDrink)
REQUIRE f.normalized_name IS UNIQUE;
