"""One-shot: scale professional-batch specialty recipes to home quantities.

Targets: syrups/culinary ~200 mL · spirit infusions 375 mL · tinctures 100 mL
· nothing over 500 mL. Ratio-based and already-small recipes untouched.
"""
import json

SCALED = {

'avocado-syrup': """- 30 mL filtered water
- 50 g sugar
- 50 mL lime juice
- 50 g soft avocado flesh

In a small bowl, combine the water and sugar and stir until dissolved. Add the lime juice and avocado, blend with an immersion blender until smooth, and then strain through a chinois. Store in an airtight container, refrigerated, for up to 2 days.

MAKES ~200 mL (scaled from 3.8 L batch)
Source: NoMad""",

'banana-oloroso': """- 375 mL Lustau Oloroso Sherry
- 1–2 overripe/black bananas, peeled
- 1.5 mg Pectin X

Blend together the sherry, bananas, and pectin. Add to a Spinzall and put on continuous until the liquid becomes clear, then strain through a chinois. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~375 mL (scaled from 1 L batch)
Source: NoMad""",

'basil-fennel-syrup': """- 30 g basil leaves
- 30 g fennel, roughly chopped
- 250 g Simple Syrup
Brix: 48

Combine the basil, fennel, and simple syrup in an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by pushing the nozzle out quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 800 g batch)
Source: NoMad""",

'brown-butter-falernum': """- 60 g unsalted butter, cubed
- 200 mL Falernum

In a small pot over medium heat, melt the butter, whisking constantly, while the milk solids brown evenly. Continue to let brown, whisking, until the color is as dark as an almond skin. Remove from the heat and add the falernum. Transfer to a storage container and place in the freezer until the fat has risen to the top and solidified. Remove and discard the solidified fat cap. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 1 L batch)
Source: NoMad""",

'cacao-nib-infused-brandy': """- 75 g cacao nibs
- 375 mL Pierre Ferrand 1840 Cognac

Combine the cacao nibs and Cognac in an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by pushing the nozzle out quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'cacao-nib-infused-blanco-tequila': """- 75 g cacao nibs
- 375 mL Blanco Tequila

Combine the cacao nibs and tequila in an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by pushing the nozzle out quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'celery-rootinfused-blanc-vermouth': """- 250 g celery root, peeled and diced
- 375 mL Dolin de Chambery Blanc vermouth

Preheat the oven to 200°C/400°F and line a sheet pan with parchment paper. Place the celery root on the prepared sheet pan and roast until dark golden brown, 25 to 30 minutes. In a bowl, combine the celery root and vermouth, let steep for 1 hour, and then strain through a chinois. Store in an airtight container, refrigerated, for up to 8 weeks.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'chai-infused-cocchi-vermouth-di-torino': """- 15 g chai tea
- 375 mL Cocchi Vermouth di Torino

In a bowl, combine the tea and vermouth, let steep for 3 to 5 minutes (taste as you go because it becomes tannic very quickly), and then strain through a chinois. Store in an airtight container, refrigerated, for up to 6 weeks.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'chai-turmeric-syrup': """- 5 g chai tea
- 140 g hot filtered water
- 140 g sugar
- 0.15 g xanthan gum
- 1.5 g Arabic gum
- 0.75 g turmeric

(A 0.01 g precision scale helps for the gums and turmeric.)

Steep the tea in the hot water for 12 minutes. Pass the liquid through a chinois, but do not press the loose tea, as the liquid will be bitter. Add the sugar and stir until fully dissolved, then transfer the mixture to a blender. While blending, sift in the xanthan gum, then the Arabic gum, and then the turmeric. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 4 L batch)
Source: NoMad""",

'chai-turmeric-yogurt-syrup': """- 100 mL Chai-Turmeric Syrup (preceding recipe)
- 100 mL unsweetened sheep's milk yogurt

In a small bowl, combine the syrup and yogurt and stir until fully incorporated. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 1 L batch)
Source: NoMad""",

'chamomile-honey-syrup': """- 10 g chamomile tea
- 100 g hot filtered water
- 150 g clover honey
Brix: 60

Steep the tea in the hot water for 3 minutes. Pass the liquid through a chinois, but do not press the loose tea, as the liquid will be bitter. Add the honey and stir until fully dissolved. Let the syrup cool to room temperature. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 575 g batch)
Source: NoMad""",

'chicken-jus': """- 20 g canola oil
- 110 g diced onions (2 cm)
- 50 g peeled and diced carrots (2 cm)
- 50 g diced celery (2 cm)
- 20 g tomato paste
- 150 mL red wine
- 900 g chicken wings
- 500 g chicken feet
- 2.7 kg water
- 1 bay leaf
- 2 thyme sprigs
- 5 black peppercorns

Preheat the oven to 200°C/400°F (convection if available). In a roasting pan over high heat, warm the canola oil. Add the onions, carrots, and celery and sauté until they caramelize, about 12 minutes. Add the tomato paste and sauté until caramelized, 3 minutes more. Add the red wine and reduce by half, about 10 minutes, then set aside. Spread the chicken wings in a single layer on a rimmed baking sheet and roast until caramelized, about 50 minutes, rotating the pan once. Drain and discard any rendered fat. Scrape the roasted wings into a stockpot and add the chicken feet and water. Bring to a simmer over medium heat, skimming the stock of all impurities and fats that rise to the top. Add the vegetable mixture to the stock, along with the bay leaf, thyme, and peppercorns. Turn the heat to low and simmer, uncovered, for 6 hours, skimming every 30 minutes. Strain the stock through a chinois, transfer to a clean saucepan, and continue to reduce over low heat until it is ~200 g. Strain the reduced jus through a chinois and chill over an ice bath. Store in an airtight container, refrigerated, for up to 3 days or freeze for up to 1 month.

MAKES ~200 g (scaled from 1 kg batch)
Source: NoMad""",

'cinnamon-orange-tea-infused-sweet-vermouth': """- 1½ heaping tbsp cinnamon-orange tea
- 375 mL sweet vermouth

Combine in a glass container for 1.5 hours, stirring occasionally, before straining through a coffee filter.

MAKES ~375 mL (scaled from 750 mL batch)""",

'coconut-oil-washed-bourbon': """- 3 oz unrefined coconut oil
- 375 mL bourbon

Combine coconut oil and bourbon in a glass container, shake to mix, and let infuse at room temperature for 6 hours. Transfer to freezer to solidify oil overnight. Discard solids and strain bourbon through a coffee filter.

Makes ~375 mL (scaled from 750 mL batch)
Source: Tiki: Modern Tropical Cocktails""",

'coffee-infused-angostura-bitters': """- 50 mL Cold Brew Coffee Concentrate
- 50 mL Angostura bitters

In a small bowl, combine the coffee concentrate and Angostura bitters and stir until fully incorporated. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~100 mL (scaled from 500 mL batch)
Source: NoMad""",

'coffee-infused-dry-vermouth': """- 38 g whole coffee beans
- 375 mL Dry vermouth

Crush the coffee beans in a spice mill or coffee grinder until very coarsely ground. Put them into an iSi canister. Add the vermouth and seal the canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by squeezing the nozzle quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Let the liquid cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~375 mL (scaled from 500 mL batch)
Source: NoMad""",

'cranberry-syrup': """- 500 g frozen cranberries
- 500 g cranberry juice
- 125 g demerara sugar
Brix: 50

In a saucepan, combine the cranberries and cranberry juice and bring to a boil over high heat. Lower the heat and simmer until all of the cranberries have popped. Remove the saucepan from the heat and let it sit for 10 minutes. Strain the mixture through a chinois and cheesecloth or through a superbag. Add the sugar and stir until fully dissolved. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 1 kg batch)
Source: NoMad""",

'dill-syrup': """- 45 g fresh dill
- 250 g Simple Syrup
Brix: 48

Add the dill and simple syrup to an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by squeezing the nozzle quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 800 g batch)
Source: NoMad""",

'earl-grey-syrup': """- 4 g Earl Grey tea
- 130 g hot water
- 120 g sugar
Brix: 48

Steep the tea in the hot water for 3 minutes. Strain the tea and add the sugar, stirring until it's fully dissolved. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 1.7 kg batch)
Source: NoMad""",

'earl-grey-milk-washed-blanco-tequila': """- 12 g Earl Grey tea
- 375 mL Excellia Blanco tequila
- 8 mL lemon juice
- 50 mL whole milk

In an airtight jar, combine the tea and tequila, let steep for 20 minutes, and then strain. In a small saucepan over medium heat, combine the lemon juice and milk and let simmer (do not boil) so the milk starts to curdle. Pour the curdled mixture into the infused tequila, whisk well, and then let sit for 30 minutes. Strain the mixture through a superbag or a coffee filter. Store in an airtight container, refrigerated, for up to 2 months.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'eucalyptus-bay-leaf-syrup': """- 1 fresh bay leaf
- 135 mL hot filtered water
- 135 g sugar
- 0.15 g eucalyptus oil

(Use a 0.01 g precision scale for the eucalyptus oil — it is very potent.)

Steep the bay leaf in the hot water for 5 minutes. Add the sugar and stir until fully dissolved. Stir in the eucalyptus oil. Pass through a chinois and let cool to room temperature. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 1.5 L batch)
Source: NoMad""",

'fig-leaf-syrup': """- 10 g fresh fig leaves
- 130 mL hot water
- 115 g sugar
Brix: 50

Rinse the fig leaves thoroughly under cool running water until the water runs clear, then remove the stems and tear up the leaves. Steep the leaves and hot water in a container for 10 to 15 minutes (taste as you go because it becomes bitter very quickly). Strain through a chinois and stir in the sugar until it dissolves. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 1.4 L batch)
Source: NoMad""",

'gardenia-syrup': """- 180 g clover honey
- 180 g unsalted butter, cubed
- 14 g allspice dram
- 14 g Vanilla Syrup
- 30 g Cinnamon Syrup

In a small saucepan over medium heat, warm the honey until it starts to become liquid. (Be sure it does not get too hot or it will thicken.) Add the butter and whisk until it is melted and the mixture is smooth. Let sit for 5 minutes, then whisk in the dram, vanilla syrup, and cinnamon syrup and let cool. Store in an airtight container, refrigerated, for up to 4 weeks.

MAKES ~200 mL (scaled from 2 L batch)
Source: NoMad""",

'ginger-lime-syrup': """- 100 g water
- 135 g light brown sugar
- 50 g ginger, chopped
- 3 g lime zest
- 15 g lime juice
Brix: 50

In a small saucepan over medium heat, combine the water, brown sugar, and ginger and simmer for 45 minutes, stirring occasionally. Remove from the heat and add the lime zest. Allow to steep for 30 minutes. Strain out the ginger and lime zest and add the lime juice. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 1.5 kg batch)
Source: NoMad""",

'green-tea-syrup': """- 5 g green tea
- 140 g hot water
- 40 g sugar
- 0.15 g xanthan gum
- 1.5 g Arabic gum

(A 0.01 g precision scale helps for the gums.)

Steep the tea in the hot water for 12 minutes. Pass the liquid through a chinois, but do not press the loose tea, as the liquid will be bitter. Add the sugar and stir until fully dissolved, then transfer the mixture to a blender. While blending at medium speed, sift in the xanthan gum and then the Arabic gum. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 3.8 L batch)
Source: NoMad""",

'green-tea-yogurt-syrup-1': """- 100 mL Green Tea Syrup (preceding recipe)
- 100 mL unsweetened sheep's milk yogurt

In a small bowl, combine the tea syrup and yogurt and stir until fully incorporated. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 1 L batch)
Source: NoMad""",

'guava-syrup': """- 45 mL filtered water
- 85 g guava puree
- Sugar as needed
Brix: 50

In a small container, whisk together the water and guava puree. Stir in the sugar to taste. Store in an airtight container, refrigerated, for up to 2 weeks.

MAKES ~200 mL (scaled from 4.7 L batch)
Source: NoMad""",

'horseradish-tincture': """- 20 g horseradish, washed, peeled, and diced
- 100 mL vodka

In a small bowl, combine the horseradish and vodka and let steep for 10 minutes, then strain through a chinois. Store in an airtight container at room temperature indefinitely.

MAKES ~100 mL (scaled from 750 mL batch)
Source: NoMad""",

'horseradish-infused-gin': """- 75 g horseradish, washed, peeled, and sliced lengthwise
- 375 mL Plymouth gin

Combine the horseradish and gin in a bag and vacuum seal. Cook sous vide (or steam) for 30 minutes at 60°C/140°F, then strain through a chinois. Store in an airtight container, refrigerated, for up to 6 weeks.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'jalape-o-infused-agave-syrup': """- 1 medium jalapeño
- 60 g hot water
- 185 g organic light blue agave nectar

Dice the jalapeño, retaining all the seeds, and steep in the hot water for 3 minutes. Taste the mixture to ensure that the spice level is to your taste. Allow it to steep longer for a spicier end product. Strain out the jalapeño when the desired spice level has been reached and stir the agave nectar into the jalapeño-infused water until it's fully integrated. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 1.1 kg batch)
Source: NoMad""",

'jalape-o-infused-tequila': """- 2–3 medium jalapeños, diced
- 375 mL Blanco tequila

Steep the jalapeños and tequila in a container for 5 minutes. Taste the mixture to ensure that the spice level is to your taste. Allow to steep longer for a spicier end product. Strain out the jalapeños when the desired spice level has been reached. Store in an airtight container, refrigerated, indefinitely.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'kabocha-squash-syrup-1': """- 125 g Kabocha Squash Water (following recipe)
- 125 g demerara sugar
Brix: 50

In a small saucepan over medium heat, heat the squash water until it's simmering. Remove from the heat and stir the sugar into the water until fully dissolved. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 1.6 kg batch)
Source: NoMad""",

'kabocha-squash-syrup': """- ¼ kabocha squash, seeded
- 320 g water
- 1.2 g salt
- 3 g whole allspice
- 20 g Ceylon cinnamon sticks, crushed

Preheat the oven to 200°C/400°F. Place the squash on a sheet pan and roast for 1½ hours. When cool enough to handle, scoop out the flesh of the squash, discarding the rest. Measure out 180 g of the roasted squash and add to a saucepan along with the water, salt, allspice, and cinnamon. Boil over high heat for 10 minutes. Strain the mixture through a chinois. Let the water cool to room temperature and store in an airtight container, refrigerated, for up to 1 week.

MAKES ~200 g (scaled from 1 kg batch)
Source: NoMad""",

'lapsang-souchong-infused-crème-de-cacao': """- 10 g Lapsang Souchong black tea
- 375 mL Crème de cacao

Combine the tea and crème de cacao in a container and let steep for 45 minutes, then strain the mixture through a chinois. Store in an airtight container, refrigerated, indefinitely.

MAKES ~375 mL (scaled from 1 L batch)
Source: NoMad""",

'lavender-infused-honey-syrup': """- 4 g dried lavender flowers
- 150 g clover honey
- 100 g hot water
Brix: 60

Stir the lavender flowers and honey into the hot water until the honey is fully dissolved. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 575 g batch)
Source: NoMad""",

'lemon-verbena-syrup': """- 5 g dried lemon verbena
- 130 g hot water
- 120 g sugar
Brix: 48

Steep the lemon verbena in the hot water for 5 minutes. Strain the mixture and stir in the sugar until it's fully dissolved. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 1.7 kg batch)
Source: NoMad""",

'lemon-verbenainfused-buttermilk': """- 100 mL Lemon Verbena Syrup (preceding recipe)
- 100 mL buttermilk

In a small bowl, combine the syrup and buttermilk and stir until fully incorporated. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~200 mL (scaled from 1 L batch)
Source: NoMad""",

'mint-infused-bourbon': """- 18 g mint leaves
- 375 mL Old Forester 86 bourbon

Combine the mint and bourbon in an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by pushing the nozzle out quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Store in an airtight container, refrigerated, indefinitely.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'mushroom-broth': """- 20 g dried shiitake mushrooms
- 200 mL hot water

In a bowl, combine the mushrooms and hot water and let steep for 30 minutes. Strain the mixture through a coffee filter and let come to room temperature. Store in an airtight container, refrigerated, for up to 1 week.

MAKES ~200 mL (scaled from 1 L batch)
Source: NoMad""",

'rhubarb-shrub': """- 3 g salt
- 15 g sugar
- 80 g white balsamic vinegar
- 80 g water
- 75 g rhubarb, washed and cut into 1-inch pieces
- 1 drop red food coloring (optional)

In a bowl, combine the salt, sugar, vinegar, and water and stir to make a brine. Combine the brine and rhubarb in a bag and vacuum seal. Cook sous vide (or steam) for 15 minutes at 63°C/145°F. Transfer the bag to the refrigerator and let chill, then strain the liquid through a chinois and stir in the food coloring. Store in an airtight container, refrigerated, indefinitely.

MAKES ~200 mL (scaled from 2.5 L batch)
Source: NoMad""",

'spicy-ginger-syrup': """- 125 g ginger juice
- 125 g turbinado sugar
Brix: 50

To make the juice, run whole stalks of ginger through an auger or masticating juicer. Strain the juice through a chinois and cheesecloth or through a superbag, straining out the lighter colored starches that remain on the bottom of the container. Warm the juice in a small saucepan over medium heat until it's just under a simmer. Add the sugar and stir to dissolve. Let the syrup cool to room temperature and store in an airtight container, refrigerated, for up to 2 weeks.

MAKES ~250 g (scaled from 500 g batch)
Source: NoMad""",

'tellicherry-black-pepper-syrup': """- 45 g Tellicherry black pepper, coarsely ground
- 250 g Demerara Syrup

Combine the pepper and syrup in an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by pushing the nozzle out quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 800 g batch)
Source: NoMad""",

'thai-bird-chile-infused-aperol': """- 5 Thai bird chiles, diced
- 375 mL Aperol

Steep the chiles and Aperol in a container for 5 minutes. Taste the mixture to ensure that the spice level is to your liking. Allow to steep longer for a spicier end product. Strain out the chiles when the desired spice level has been reached. Store in an airtight container, refrigerated, indefinitely.

MAKES ~375 mL (scaled from 750 mL batch)
Source: NoMad""",

'vanilla-syrup': """- 250 g Simple Syrup
- 1 vanilla bean, split

Combine the simple syrup and vanilla in an iSi canister. Charge it twice using N2O (cream) chargers, shaking the canister between each charge. Allow the canister to sit for 5 minutes and then vent by pushing the nozzle out quickly; place a container underneath the tip to catch any liquid that may be released. Unscrew the top of the canister. Once the liquid stops bubbling, strain the mixture through cheesecloth or a coffee filter. Store in an airtight container, refrigerated, for up to 1 month.

MAKES ~250 g (scaled from 800 g batch)
Source: NoMad""",

'falernum': """- 0.25 g star anise
- 0.25 g mace
- 0.3 g nutmeg, grated
- 0.5 g cloves
- 4 g lime peel
- 8 g ginger, thinly sliced
- 10 mL aged overproof rum (Hamilton 151)
- 40 mL unaged overproof Jamaican rum (Wray & Nephew)
- 0.2 mL almond extract
- 5 mL strained or clarified lemon juice
- 15 mL strained or clarified lime juice
- 80 mL 2:1 cane syrup
- 250 mL (estimated) 1:1 gum syrup

(A 0.01 g precision scale helps for the spices.)

Grind dry spices with a mortar and pestle or spice grinder. Combine lime peel, ginger, and rums in a blender on high until ginger is liquefied and lime peel is thoroughly minced.

Combine rum mixture and ground spices in a vacuum bag and seal. Place in a water bath at 125ºF for 12 hours or in the refrigerator for 24 hours.

Finely strain mixture through a nutmilk bag, squeezing to maximize yield, and then pass through a coffee filter. Yield should be ~75%.

Add almond extract, juices, and syrup. This should yield ~250 mL liquid. Combine with an equal volume of gum syrup.

MAKES ~500 mL (scaled from 55 oz batch)
Source: Tropical Standard (p. 232)""",

'fermented-aroma': """- 400 g ripe tomatoes (the best you can get)
- 8–10 g sea salt

Cut tomatoes into quarters or eighths and mix with salt in a bowl. Transfer to a zip lock or vacuum seal bag. If using a vacuum bag, vac and you're good to go. If not, submerge bag in water to remove the air and close. Let ferment until desired funkiness.

Strain through a nut milk bag, squeezing to get all liquid out. Save solids for projects like fermented pizza sauce.

Liquid will mostly clarify if allowed to rack for a few days. A centrifuge and coffee filter will help.

MAKES ~200 mL (scaled from 1 kg batch)""",

}

p = json.load(open('Data/pantry.json'))
by_id = {s['id']: s for s in p['specialty']}
missing = [k for k in SCALED if k not in by_id]
if missing:
    raise SystemExit(f"IDs not found: {missing}")

for sid, recipe in SCALED.items():
    by_id[sid]['recipe'] = recipe

json.dump(p, open('Data/pantry.json', 'w'), indent=2, ensure_ascii=False)
print(f"Scaled {len(SCALED)} specialty recipes.")
