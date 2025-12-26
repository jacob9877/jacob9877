/*
This is a simple text translation program that uses the RapidAPI Text Translator API to translate text from one language to another. 
It also displays the translated text in a graphical user interface (GUI) window using the Tkinter library.
*/
import requests
import tkinter as tk

/*
These lines import the necessary libraries: requests for making HTTP requests to the translation API, and tkinter for creating the GUI window.
*/
def print_supported_languages():
    print("""
| Language Name        | Language Code |
|----------------------|---------------|
| Afrikaans            | af            |
| Albanian             | sq            |
| Amharic              | am            |
| Arabic               | ar            |
| Armenian             | hy            |
| Azerbaijani          | az            |
| Basque               | eu            |
| Belarusian           | be            |
| Bengali              | bn            |
| Bosnian              | bs            |
| Bulgarian            | bg            |
| Catalan              | ca            |
| Cebuano              | ceb           |
| Chichewa             | ny            |
| Chinese (Simplified) | zh-CN         |
| Chinese (Traditional)| zh-TW         |
| Corsican             | co            |
| Croatian             | hr            |
| Czech                | cs            |
| Danish               | da            |
| Dutch                | nl            |
| English              | en            |
| Esperanto            | eo            |
| Estonian             | et            |
| Filipino             | tl            |
| Finnish              | fi            |
| French               | fr            |
| Frisian              | fy            |
| Galician             | gl            |
| Georgian             | ka            |
| German               | de            |
| Greek                | el            |
| Gujarati             | gu            |
| Haitian Creole       | ht            |
| Hausa                | ha            |
| Hawaiian             | haw           |
| Hebrew               | iw / he       |
| Hindi                | hi            |
| Hmong                | hmn           |
| Hungarian            | hu            |
| Icelandic            | is            |
| Igbo                 | ig            |
| Indonesian           | id            |
| Irish                | ga            |
| Italian              | it            |
| Japanese             | ja            |
| Javanese             | jw            |
| Kannada              | kn            |
| Kazakh               | kk            |
| Khmer                | km            |
| Kinyarwanda          | rw            |
| Korean               | ko            |
| Kurdish (Kurmanji)   | ku            |
| Kyrgyz               | ky            |
| Lao                  | lo            |
| Latin                | la            |
| Latvian              | lv            |
| Lithuanian           | lt            |
| Luxembourgish        | lb            |
| Macedonian           | mk            |
| Malagasy             | mg            |
| Malay                | ms            |
| Malayalam            | ml            |
| Maltese              | mt            |
| Maori                | mi            |
| Marathi              | mr            |
| Mongolian            | mn            |
| Myanmar (Burmese)    | my            |
| Nepali               | ne            |
| Norwegian            | no            |
| Odia (Oriya)         | or            |
| Pashto               | ps            |
| Persian              | fa            |
| Polish               | pl            |
| Portuguese           | pt            |
| Punjabi              | pa            |
| Romanian             | ro            |
| Russian              | ru            |
| Samoan               | sm            |
| Scots Gaelic         | gd            |
| Serbian              | sr            |
| Sesotho              | st            |
| Shona                | sn            |
| Sindhi               | sd            |
| Sinhala              | si            |
| Slovak               | sk            |
| Slovenian            | sl            |
| Somali               | so            |
| Spanish              | es            |
| Sundanese            | su            |
| Swahili              | sw            |
| Swedish              | sv            |
| Tajik                | tg            |
| Tamil                | ta            |
| Tatar                | tt            |
| Telugu               | te            |
| Thai                 | th            |
| Turkish              | tr            |
| Turkmen              | tk            |
| Ukrainian            | uk            |
| Urdu                 | ur            |
| Uyghur               | ug            |
| Uzbek                | uz            |
| Vietnamese           | vi            |
| Welsh                | cy            |
| Xhosa                | xh            |
| Yiddish              | yi            |
| Yoruba               | yo            |
| Zulu                 | zu            |

    
    """)

print_supported_languages()

/*
This function prints a list of supported languages and their corresponding language codes. It's called at the beginning of the program to 
provide information to the user.
*/
def translate_text():
    url = "https://text-translator2.p.rapidapi.com/translate"

    source = input("Please input your source language: ")
    target = input("Please input your target language: ")
    text = input("Please input your text: ")

    payload = {
        "source_language": source,
        "target_language": target,
        "text": text
    }
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "X-RapidAPI-Key": "41594882bamsh3afc3d8223b26c9p1488c6jsn8e057fa1a11b",
        "X-RapidAPI-Host": "text-translator2.p.rapidapi.com"
    }

    response = requests.post(url, data=payload, headers=headers)
    response_data = response.json()
    print(response.json())
    if response_data['status'] == 'success':
        translated_text = response_data['data']['translatedText']
        root = tk.Tk()
        label = tk.Label(root, text=translated_text, font=("Arial", 39))
        label.pack()
        root.mainloop()
    return translated_text
print(f'The translated text is: {translate_text()}')

