"""First names and surnames for generation briefs and name-swap augmentation."""

# Held out of every training brief so the hand-written examples test unseen names.
HELD_OUT_NAMES = {"Maya", "Daniel", "Alex", "Priya"}

NAMES = """
Aaliyah Aarav Abdi Abebe Abigail Adaeze Adebayo Aditi Adriana Afua Agnieszka Ahmed Aidan Aiko Aisha Akira Alana Alejandro
Aleksander Alessia Alfie Ali Alice Alina Amara Amir Amy Ana Anan Anders Andile Andre Aneesh Angela Anika Anil Anjali
Ann Antoine Anya Aoife Archie Arjun Arturo Asha Astrid Aurelio Ava Ayesha Ayo Bao Barbara Beatriz Ben Bethany Bilal
Björn Blessing Bogdan Bridget Bruno Caitlin Callum Camila Carlos Carmen Caroline Catalina Cem Chantal Chen Chiara Chidi
Chioma Chloe Chris Ciara Claire Colm Connor Dafydd Dalia Damian Dana Darius Dawit Deepa Delroy Demi Dev Dimitri Divya
Dmitri Dong Dorota Duc Eamon Ebony Eduardo Efua Eilidh Elena Eli Elif Elijah Ellie Emeka Emil Emily Emre Erin Esme
Esther Ethan Eva Fang Farah Farid Fatima Felix Femi Fern Finn Fiona Florin Francesca Freya Gabriel Gareth Gemma Georgia
Gintaras Giulia Grace Graham Gustavo Hadiza Hamza Hana Hannah Haruto Hassan Heather Helen Hemi Henrik Hiroshi Hoang
Hugo Ibrahim Idris Ifeoma Ignacio Ilse Imani Imogen Ines Ioana Irina Isaac Isabel Isla Ivan Jack Jada Jakub James Jamal
Jasmine Javier Jaya Jen Jess Jin Joanna Joe Jonah Jorge Joseph Joy Juan Julia Julien Jun Kai Kaito Kalani Karan Karim
Kasia Kate Katarzyna Kavya Keisha Kemal Kenji Kerry Kevin Khadija Kiara Kieran Kiri Kofi Krisztina Kwame Lachlan Laila
Lars Laura Layla Leah Lena Leon Liam Lila Lin Lindiwe Lior Lola Lorenzo Louis Luca Lucy Luis Lukas Lwazi Mabel Magda
Mai Malik Mandla Manon Marcus Mariam Marisol Marta Mateo Matilda Matteo Mehmet Mei Meera Mia Michael Mihai Mila Milan
Ming Miriam Mohammed Moira Mustafa Nadia Naledi Nasser Natasha Neha Nia Niamh Nikhil Nikolai Nina Noah Noor Nora Obi
Oisín Olga Oliver Olivia Omar Oscar Owen Paolo Patrick Pedro Petra Phoebe Pieter Pooja Rachel Rafael Rahul Rana Ravi
Rebecca Reggie Reza Rhys Ricardo Rin Rohan Rosa Rory Ruby Ryan Saanvi Sadia Salma Sam Samir Sana Santiago Sara Saskia
Sean Seo-yeon Shanice Shira Shreya Simone Sinead Siobhan Siddharth Sofia Sophie Stefan Sunil Suzanne Svetlana Tadhg
Tamar Tanvi Tariq Tendai Teresa Thabo Theo Thomas Tiago Tobi Tomás Tunde Uma Valentina Vanessa Varun Vera Victor
Vikram Wei Wiremu Xavier Ximena Yara Yasmin Yaw Yetunde Yosef Yuki Yusuf Zainab Zara Zeynep Zhang Zoe Zofia
""".split()

SURNAMES = """
Adeyemi Ahmed Andersson Baker Banerjee Barros Bianchi Brennan Chen Costa Dubois Evans Fernández Fischer Garcia
Gonzalez Gupta Haddad Hughes Ibrahim Ito Jensen Johnson Kaur Khan Kim Kowalski Kumar Le Lee Lewis Lopez MacDonald Mensah
Moreau Morris Murphy Nakamura Nguyen Novak Nowak O'Brien Okafor Olsen Osei Patel Petrov Popescu Reyes Rossi Santos Sato
Schmidt Shah Singh Smith Suzuki Tanaka Thomas Usman Walsh Wang Williams Wright Yilmaz Zhou
""".split()

TRAIN_NAMES = [n for n in NAMES if n not in HELD_OUT_NAMES]
